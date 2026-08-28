import time
import json
import logging
import threading
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SessionLocal, MonitorConfig, PushSubscription, User, Tenant, ScraperAccount
from core.session_manager import SessionManager
from core.adapters.adapter_factory import AdapterFactory
import core.adapters.gvc_adapter  # Ensure adapters are registered

import tempfile

_vapid_env = os.getenv("VAPID_PRIVATE_KEY")
if _vapid_env and "-----BEGIN PRIVATE KEY-----" in _vapid_env:
    pem_data = _vapid_env.replace('\\n', '\n')
    temp_pem_path = os.path.join(tempfile.gettempdir(), "vapid_private_key.pem")
    with open(temp_pem_path, "w") as f:
        f.write(pem_data)
    VAPID_PRIVATE_KEY = temp_pem_path
elif _vapid_env:
    VAPID_PRIVATE_KEY = _vapid_env.replace('\\n', '\n')
else:
    VAPID_PRIVATE_KEY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "private_key.pem")
VAPID_CLAIMS = {"sub": "mailto:admin@samwebdevs.dpdns.org"}

class SlotMonitorEngine(threading.Thread):
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self.daemon = True
        self.previously_seen_slot_ids = set()
        self.session_manager = SessionManager()
        self.base_url = os.getenv('BOOKING_PORTAL_URL', "https://pk-gr-services.gvcworld.eu")
        
    def stop(self):
        logging.info("Stopping Cloud Slot Monitor Engine...")
        self._stop_event.set()
        self._wake_event.set()

    def send_push_notifications(self, db: Session, message: str):
        subscriptions = db.query(PushSubscription).join(User).join(Tenant).filter(
            User.is_active == True,
            Tenant.is_active == True
        ).all()
        
        payload = json.dumps({
            "title": "KE Agent Slot Alert!",
            "body": message,
            "url": "/"
        })
        
        for sub in subscriptions:
            try:
                sub_info = {
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                }
                webpush(
                    subscription_info=sub_info,
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
            except WebPushException as ex:
                logging.error(f"Push failed for user {sub.user_id}: {repr(ex)}")
                if ex.response is not None and ex.response.status_code in [404, 410]:
                    db.delete(sub)
                    db.commit()
            except Exception as e:
                logging.error(f"Push error: {e}")

    def search_slots(self, session, date_from: str, app_type: str, vac_id: str, provider: str = "GVC"):
        try:
            adapter = AdapterFactory.get_adapter(provider, headless=True)
            # The adapter takes care of the endpoint and payload specifics
            slots = adapter.search_slots(session, date_from, app_type, vac_id)
            return slots
        except Exception as e:
            logging.error(f"Exception during abstract search_slots: {e}")
            return None

    def run(self):
        logging.info("Cloud Slot Monitor Engine started.")
        while not self._stop_event.is_set():
            db = SessionLocal()
            interval_seconds = 30
            try:
                config = db.query(MonitorConfig).first()
                if not config or not config.is_active:
                    logging.info("Monitor is inactive or not configured. Sleeping for 30s...")
                    self._wake_event.wait(30)
                    self._wake_event.clear()
                    continue
                    
                strategy = config.captcha_strategy.upper()
                if strategy == 'AUTO' and not config.captcha_api_key:
                    logging.error("Auto Captcha API Key missing.")
                    self._wake_event.wait(30)
                    self._wake_event.clear()
                    continue
                    
                interval_seconds = config.interval_minutes * 60
                holidays = [h.strip().upper() for h in config.holidays.split(',') if h.strip()]
                sitekey = os.getenv('TARGET_SITEKEY', '6LcnlCoUAAAAAJLjWXXaByTFyuOLf4K0gGu5r3d2')
                
                try:
                    start_date = datetime.strptime(config.date_from, "%d/%m/%Y")
                    end_date = datetime.strptime(config.date_to, "%d/%m/%Y")
                except ValueError:
                    logging.error("Invalid date format in config.")
                    self._wake_event.wait(60)
                    self._wake_event.clear()
                    continue
                    
                dates_to_check = []
                current_date = start_date
                all_valid_dates = []
                while current_date <= end_date:
                    # Skip weekends (Saturday=5, Sunday=6) - Visa centers are closed on weekends
                    if current_date.weekday() >= 5:
                        current_date += timedelta(days=1)
                        continue
                    if current_date.strftime("%a").upper() in holidays or current_date.strftime("%A").upper() in holidays:
                        current_date += timedelta(days=1)
                        continue
                    all_valid_dates.append(current_date)
                    current_date += timedelta(days=1)
                    
                # GVC Code 2 (National Visa Long Term Type D) operates on Thursday & Friday only
                if str(config.app_type).strip() in ["2", "National Visa", "NationalVisa"]:
                    operating_dates = [d.strftime("%d/%m/%Y") for d in all_valid_dates if d.weekday() in [3, 4]]
                    non_operating_dates = [d.strftime("%d/%m/%Y") for d in all_valid_dates if d.weekday() not in [3, 4] and d.weekday() < 5]
                    if operating_dates:
                        dates_to_check = operating_dates + ([non_operating_dates[0]] if non_operating_dates else [])
                    else:
                        dates_to_check = [d.strftime("%d/%m/%Y") for d in all_valid_dates]
                else:
                    # GVC Codes 26 (Seasonal/Dependent Employment), 6 (Prime Time), and 5 (Premium Lounge) operate Mon-Fri
                    dates_to_check = [d.strftime("%d/%m/%Y") for d in all_valid_dates]
                    
                if not dates_to_check:
                    self._wake_event.wait(60)
                    self._wake_event.clear()
                    continue
                    
                accounts = db.query(ScraperAccount).filter(ScraperAccount.is_active == True).all()
                if not accounts:
                    logging.error("No active Scraper Accounts found in database!")
                    self._wake_event.wait(60)
                    self._wake_event.clear()
                    continue
                
                available_slots = []
                scraper_success = False
                
                for account in accounts:
                    logging.info(f"Checking slots using account {account.username}...")
                    
                    try:
                        # 1. Ask SessionManager for a ready-to-use HTTP session (this might trigger Playwright headlessly)
                        session = self.session_manager.get_session(
                            username=account.username,
                            password=account.password,
                            sitekey=sitekey,
                            captcha_api_key=config.captcha_api_key
                        )
                        
                        if not session:
                            logging.error(f"Could not acquire session for {account.username}. Skipping to next account.")
                            continue
                            
                        account_failed = False
                        
                        for target_date in dates_to_check:
                            if self._stop_event.is_set(): break
                            
                            if config.is_demo:
                                logging.info("DEMO MODE ACTIVE. Simulating slot discovery...")
                                time.sleep(5)
                                self.send_push_notifications(db, "DEMO SLOT FOUND: 10:00")
                                scraper_success = True
                                break
                            
                            # 2. Use adapter to search slots
                            # Fallback to "GVC" if provider isn't in config yet (will add to models next)
                            provider = getattr(config, 'provider', 'GVC')
                            slots = self.search_slots(session, target_date, config.app_type, config.vac_id, provider)
                            
                            if slots is None:
                                logging.error(f"Network or Auth error during search for {target_date} using {account.username}.")
                                account_failed = True
                                break
                            
                            for slot in slots:
                                if slot.get('isavailable') and slot.get('isselectable'):
                                    available_slots.append({"id": slot['id'], "time": slot['starttime'], "date": target_date})
                                    
                            if available_slots:
                                break
                                
                            time.sleep(2)
                            
                        if not account_failed:
                            scraper_success = True
                            break
                            
                    except Exception as e:
                        logging.error(f"Exception during scraping with {account.username}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                if not scraper_success:
                    logging.error("All scraper accounts failed! Will retry next cycle.")
                
                if not available_slots:
                    self.previously_seen_slot_ids.clear()
                else:
                    current_slot_ids = {s['id'] for s in available_slots}
                    new_slot_ids = current_slot_ids - self.previously_seen_slot_ids
                    
                    if new_slot_ids:
                        msg = f"Found {len(new_slot_ids)} NEW slots! Check the portal immediately."
                        logging.info(msg)
                        self.send_push_notifications(db, msg)
                        self.previously_seen_slot_ids.update(new_slot_ids)
                        
            finally:
                db.close()
                
            logging.info(f"Going to sleep for {interval_seconds} seconds. Waiting for next cycle or manual trigger...")
            self._wake_event.wait(interval_seconds)
            self._wake_event.clear()
