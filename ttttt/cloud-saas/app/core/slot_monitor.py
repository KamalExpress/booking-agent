import time
import json
import logging
import threading
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SessionLocal, MonitorConfig, PushSubscription, User, Tenant
from core.main_operator import OperatorAgent
from core.captcha_service import NopeChaService
from core.mock_captcha import MockCaptchaService

# In production, these should be environment variables
_vapid_env = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PRIVATE_KEY = _vapid_env.replace('\\n', '\n') if _vapid_env else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "private_key.pem")
VAPID_CLAIMS = {"sub": "mailto:admin@samwebdevs.dpdns.org"}

class SlotMonitorEngine(threading.Thread):
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self.daemon = True
        self.previously_seen_slot_ids = set()
        
    def stop(self):
        logging.info("Stopping Cloud Slot Monitor Engine...")
        self._stop_event.set()
        self._wake_event.set()

    def send_push_notifications(self, db: Session, message: str):
        # Fan-Out to all active users in active tenants
        subscriptions = db.query(PushSubscription).join(User).join(Tenant).filter(
            User.is_active == True,
            Tenant.is_active == True
        ).all()
        
        logging.info(f"Fanning out push notification to {len(subscriptions)} devices...")
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
                # If gone, delete subscription
                if ex.response is not None and ex.response.status_code in [404, 410]:
                    db.delete(sub)
                    db.commit()
            except Exception as e:
                logging.error(f"Push error: {e}")

    def run(self):
        logging.info("Cloud Slot Monitor Engine started.")
        while not self._stop_event.is_set():
            db = SessionLocal()
            interval_seconds = 30 # default
            try:
                config = db.query(MonitorConfig).first()
                if not config or not config.is_active:
                    logging.info("Monitor is inactive or not configured. Sleeping for 30s...")
                    self._wake_event.wait(30)
                    self._wake_event.clear()
                    continue
                    
                strategy = config.captcha_strategy.upper()
                if strategy == 'MOCK':
                    captcha_svc = MockCaptchaService()
                elif strategy == 'AUTO':
                    if not config.captcha_api_key:
                        logging.error("Auto Captcha API Key missing.")
                        self._wake_event.wait(30)
                        self._wake_event.clear()
                        continue
                    captcha_svc = NopeChaService(config.captcha_api_key)
                else:
                    from core.captcha_service import CloudManualCaptchaService
                    logging.info("Using Cloud Manual Captcha Service.")
                    captcha_svc = CloudManualCaptchaService()
                    
                interval_seconds = config.interval_minutes * 60
                holidays = [h.strip().upper() for h in config.holidays.split(',') if h.strip()]
                
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
                    
                # We need one central account to scrape. For MVP, we can use a mock or environment variable account.
                # In full SaaS, SuperAdmin provides a scraping pool.
                agent = OperatorAgent(captcha_service=captcha_svc, username="demo_saas@gmail.com", password="password")
                
                logging.info("Waking up to check for slots...")
                if not agent.login():
                    logging.error("Cloud Scraper failed to login. Retrying next cycle.")
                    self._wake_event.wait(interval_seconds)
                    self._wake_event.clear()
                    continue
                    
                available_slots = []
                for target_date in dates_to_check:
                    if self._stop_event.is_set(): break
                    
                    if config.is_demo:
                        logging.info("DEMO MODE ACTIVE. Simulating slot discovery...")
                        time.sleep(5)
                        self.send_push_notifications(db, "DEMO SLOT FOUND: 10:00")
                        time.sleep(30)
                        continue
                        
                    slots_response = agent.search_slots(target_date, config.app_type, config.vac_id)
                    if slots_response and slots_response.get("code") == "SUCCESS":
                        ret_obj = slots_response.get("returnobject")
                        slots = ret_obj.get("slots", []) if isinstance(ret_obj, dict) else (ret_obj if isinstance(ret_obj, list) else [])
                        for slot in slots:
                            if slot.get('isavailable') and slot.get('isselectable'):
                                available_slots.append({"id": slot['id'], "time": slot['starttime'], "date": target_date})
                                
                        if available_slots:
                            break # Found slots, break early
                            
                    time.sleep(2)
                    
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
