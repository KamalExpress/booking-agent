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
            "title": "Kamal Express Slot Alert!",
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

    def search_slots(self, session, date_from: str, app_type: str, vac_id: str):
        url = f"{self.base_url}/api/v1/periodslot/slots"
        payload = {
            "datefrom": date_from,
            "type": int(app_type),
            "bookingfor": 0,
            "members": 1,
            "method": 1,
            "travelpurposes": -1,
            "howmanyapplicantsareunder12": 0,
            "appointmentId": "undefined",
            "id": 0,
            "vac": {"id": int(vac_id)}
        }
        
        try:
            response = session.put(url, json=payload, timeout=20)
            return response
        except Exception as e:
            logging.error(f"Exception during search_slots: {e}")
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
                while current_date <= end_date:
                    if current_date.strftime("%a").upper() in holidays or current_date.strftime("%A").upper() in holidays:
                        current_date += timedelta(days=1)
                        continue
                    dates_to_check.append(current_date.strftime("%d/%m/%Y"))
                    current_date += timedelta(days=1)
                    
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
                            
                            # 2. Use lightweight curl_cffi session to poll
                            response = self.search_slots(session, target_date, config.app_type, config.vac_id)
                            
                            if response is None:
                                logging.error(f"Network error during search for {target_date} using {account.username}.")
                                account_failed = True
                                break
                            
                            if response.status_code == 429:
                                # Exponential backoff with jitter
                                backoff = random.uniform(5.0, 15.0)
                                logging.warning(f"Rate limited (429). Backing off for {backoff:.2f} seconds.")
                                time.sleep(backoff)
                                continue # retry or move to next date
                                
                            elif response.status_code in [401, 403]:
                                logging.error(f"Session expired or WAF block (401/403) for {account.username}.")
                                self.session_manager.invalidate_session(account.username)
                                account_failed = True
                                break
                                
                            elif response.status_code == 200:
                                slots_data = response.json()
                                if slots_data and slots_data.get("code") == "SUCCESS":
                                    ret_obj = slots_data.get("returnobject")
                                    slots = ret_obj.get("slots", []) if isinstance(ret_obj, dict) else (ret_obj if isinstance(ret_obj, list) else [])
                                    for slot in slots:
                                        if slot.get('isavailable') and slot.get('isselectable'):
                                            available_slots.append({"id": slot['id'], "time": slot['starttime'], "date": target_date})
                                            
                                    if available_slots:
                                        break
                                else:
                                    logging.warning(f"Unexpected JSON format from API: {slots_data}")
                            else:
                                logging.error(f"Unexpected status code {response.status_code}: {response.text}")
                                
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
