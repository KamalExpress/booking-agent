import os
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import components from existing files
from main_operator import OperatorAgent
from mock_captcha import MockCaptchaService
from captcha_service import NopeChaService

# Ensure environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Set up logging for the monitor
os.makedirs('logs', exist_ok=True)
log_filename = f"logs/monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [MONITOR] %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

def format_slots_message(slots):
    """Formats available slots into a readable HTML message for Telegram."""
    lines = ["🔔 <b>VISA SLOTS AVAILABLE!</b> 🔔", ""]
    for s in slots:
        lines.append(f"📅 <b>Date:</b> {s.get('date')} | ⏰ <b>Time:</b> {s.get('time')} | <b>ID:</b> {s.get('id')}")
    lines.append("")
    lines.append("<i>Log into the portal or run your bots immediately!</i>")
    return "\n".join(lines)

import threading
import config_manager

class SlotMonitorEngine(threading.Thread):
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self.daemon = True
        
    def stop(self):
        logging.info("Stopping Slot Monitor...")
        self._stop_event.set()
        
    def run(self):
        try:
            previously_seen_slot_ids = set()
            agent = None
            
            while not self._stop_event.is_set():
                settings = config_manager.load_settings()
                accounts = config_manager.load_accounts()
                
                if not accounts:
                    logging.error("No accounts configured! Please add an account in the GUI.")
                    self._stop_event.wait(30)
                    continue
                    
                strategy = settings.get('CAPTCHA_STRATEGY', 'MANUAL').upper()
                
                if strategy == 'MOCK':
                    logging.info("Using Mock Captcha Service for local demo.")
                    captcha_svc = MockCaptchaService()
                elif strategy == 'MANUAL':
                    from captcha_service import ManualCaptchaService
                    logging.info("Using Manual Browser Captcha Service.")
                    captcha_svc = ManualCaptchaService()
                else:
                    import os
                    capsolver_key = os.getenv('CAPSOLVER_API_KEY', '') or settings.get('CAPTCHA_API_KEY', '')
                    if capsolver_key:
                        from captcha_service import CapSolverService
                        logging.info("Using CapSolver Auto Captcha Service.")
                        captcha_svc = CapSolverService(capsolver_key)
                    else:
                        logging.error("No Auto Captcha API Key found in settings or environment.")
                        self._stop_event.wait(30)
                        continue
                    
                interval_minutes = int(settings.get('MONITOR_INTERVAL_MINUTES', 5))
                interval_seconds = interval_minutes * 60
                
                date_from_str = settings.get('APPOINTMENT_DATE_FROM', '01/09/2026')
                date_to_str = settings.get('APPOINTMENT_DATE_TO', date_from_str)
                holidays_str = settings.get('HOLIDAYS', 'SAT,SUN')
                app_type = settings.get('APPOINTMENT_TYPE', '26')
                vac_id = settings.get('APPOINTMENT_VAC_ID', '138')
                
                holidays = [h.strip().upper() for h in holidays_str.split(',') if h.strip()]
                
                try:
                    start_date = datetime.strptime(date_from_str, "%d/%m/%Y")
                    end_date = datetime.strptime(date_to_str, "%d/%m/%Y")
                except ValueError:
                    logging.error("Invalid date format in settings. Use DD/MM/YYYY")
                    self._stop_event.wait(30)
                    continue
                    
                dates_to_check = []
                current_date = start_date
                while current_date <= end_date:
                    day_name_short = current_date.strftime("%a").upper()
                    day_name_long = current_date.strftime("%A").upper()
                    if day_name_short in holidays or day_name_long in holidays:
                        current_date += timedelta(days=1)
                        continue
                    dates_to_check.append(current_date.strftime("%d/%m/%Y"))
                    current_date += timedelta(days=1)
                    
                if not dates_to_check:
                    logging.error("No valid dates to check after filtering holidays.")
                    self._stop_event.wait(30)
                    continue

                logging.info("Waking up to check for slots...")
                
                # Account Fallback Logic (Persisted across loops)
                if agent is None:
                    logging.info("Session not found or expired. Attempting to log in...")
                    login_success = False
                    for acc in accounts:
                        username = acc.get("username")
                        password = acc.get("password")
                        if not username or not password:
                            continue
                            
                        logging.info(f"Attempting initialization for {username}...")
                        temp_agent = OperatorAgent(captcha_service=captcha_svc, username=username, password=password)
                        
                        if temp_agent.session.cookies:
                            logging.info("Found saved session cookies. Skipping Captcha login for now.")
                            agent = temp_agent
                            login_success = True
                            break

                        if temp_agent.login():
                            agent = temp_agent
                            login_success = True
                            break
                        else:
                            logging.warning(f"Login failed for {username}. Trying next account if available...")
                            if self._stop_event.is_set():
                                break
                    
                    if not login_success or self._stop_event.is_set():
                        logging.error("All accounts failed to login. Will retry next cycle.")
                        agent = None
                        self._stop_event.wait(interval_seconds)
                        continue
                else:
                    logging.info("Using existing authenticated session.")
                    
                # 2. Search Slots across all dates
                demo_mode = settings.get("DEMO_MODE", "False") == "True"
                available_slots = []
                for target_date in dates_to_check:
                    if self._stop_event.is_set():
                        break
                        
                    logging.info(f"Checking slots for {target_date}...")
                    
                    if demo_mode:
                        logging.info(f"[DEMO MODE] Faking slots found for {target_date}...")
                        slots_response = {
                            "code": "SUCCESS",
                            "returnobject": {
                                "slots": [{"id": 99999, "starttime": "09:00", "isavailable": True, "isselectable": True}]
                            }
                        }
                        time.sleep(1) # Fake processing delay
                    else:
                        slots_response = agent.search_slots(target_date, app_type, vac_id)
                        
                    if slots_response is None:
                        logging.error("Session may have expired or WAF blocked the request. Discarding session to force re-login on next cycle.")
                        if agent: agent.clear_session()
                        agent = None
                        break
                    
                    if slots_response and slots_response.get("code") == "SUCCESS":
                        ret_obj = slots_response.get("returnobject")
                        if isinstance(ret_obj, dict):
                            slots = ret_obj.get("slots", [])
                        elif isinstance(ret_obj, list):
                            slots = ret_obj
                        else:
                            slots = []
                        for slot in slots:
                            if slot.get('isavailable') and slot.get('isselectable'):
                                available_slots.append({
                                    "id": slot['id'], 
                                    "time": slot['starttime'], 
                                    "date": target_date
                                })
                        
                        if available_slots:
                            logging.info(f"Slots found on {target_date}! Stopping further date checks for this cycle.")
                            break
                    else:
                        logging.error(f"Failed to fetch slots for {target_date} from the portal API.")
                        
                    # Custom sleep to allow fast cancellation
                    for _ in range(4): # 2 seconds total, check event every 0.5s
                        if self._stop_event.is_set(): break
                        time.sleep(0.5)
                        
                if self._stop_event.is_set():
                    break
                    
                if not available_slots:
                    logging.info("No slots available in the given date range.")
                    previously_seen_slot_ids.clear()
                else:
                    current_slot_ids = {s['id'] for s in available_slots}
                    new_slot_ids = current_slot_ids - previously_seen_slot_ids
                    
                    if new_slot_ids:
                        logging.info(f"Found {len(new_slot_ids)} NEW available slots! Triggering alert.")
                        notification_file = os.path.join(os.path.dirname(__file__), '..', 'slots_notification.txt')
                        message = format_slots_message([s for s in available_slots if s['id'] in new_slot_ids])
                        try:
                            with open(notification_file, 'a', encoding='utf-8') as f:
                                f.write(f"\n--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                                f.write(message + "\n")
                            previously_seen_slot_ids.update(new_slot_ids)
                            logging.info(f"Notification written to {notification_file}")
                            
                            # Play victory alarm!
                            try:
                                import winsound
                                winsound.Beep(1500, 2000)
                            except:
                                pass
                        except Exception as e:
                            logging.error(f"Failed to write notification file: {e}")
                    else:
                        logging.info("Slots are available, but an alert was already sent previously. Skipping duplicate alert.")

                logging.info(f"Going to sleep for {interval_minutes} minutes...")
                # Wait with stop event
                self._stop_event.wait(interval_seconds)
        except Exception as e:
            logging.error(f"Monitor Engine crashed unexpectedly: {e}", exc_info=True)
            self.stop()

if __name__ == "__main__":
    engine = SlotMonitorEngine()
    engine.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        engine.stop()
        engine.join()