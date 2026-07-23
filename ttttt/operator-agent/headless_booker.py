import time
import logging
import sys
import os
import threading
from dotenv import load_dotenv

from api_client import SaaSClient
from captcha_service import CapSolverService
from core.gvc_adapter import GVCAdapter

load_dotenv()

class SaaSStreamHandler(logging.Handler):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        # Simple buffer to avoid threading issues in this demo
        self.buffer = []

    def emit(self, record):
        try:
            msg = self.format(record)
            self.buffer.append(msg)
            if len(self.buffer) >= 50:
                self.api_client.stream_logs(self.buffer)
                self.buffer.clear()
        except Exception:
            pass

class BookerEngine(threading.Thread):
    def __init__(self, base_url: str):
        super().__init__(daemon=True)
        self.api = SaaSClient(base_url, cred_file="booker_creds.txt")
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logging.info("Starting Headless Booker Engine...")
        
        # 1. Register with SaaS as a Booking-capable worker
        registered = False
        for attempt in range(10):
            if self.api.register(hostname="booker-01", can_scrape=False, can_book=True):
                registered = True
                break
            logging.info(f"SaaS not ready yet (Attempt {attempt+1}/10). Retrying in 3 seconds...")
            time.sleep(3)
            
        if not registered:
            logging.error("Failed to register with SaaS after 10 attempts. Cannot start booker.")
            return
            
        # 2. Start Heartbeat thread
        self.api.start_heartbeat()
        
        while not self._stop_event.is_set():
            try:
                # 3. Pull next assignment
                lease, retry_after = self.api.get_next_lease()
                
                if not lease:
                    logging.info(f"No booking tasks available. Sleeping for {retry_after} seconds.")
                    self._stop_event.wait(retry_after)
                    continue
                    
                if "booking_task_context" not in lease:
                    logging.warning("Received a non-booking lease. Completing it immediately to avoid blocking.")
                    self.api.complete_assignment(lease["lease_id"]) # Assuming lease_id maps to assignment_id for scraper
                    continue
                    
                # 4. Parse Booking Lease
                task = lease["booking_task_context"]
                task_id = task["id"]
                account = lease["scraper_account"]
                visa_center = task["visa_center"]
                applicant_data = task["applicant_data"]
                
                logging.info(f"Received Booking Task #{task_id} for applicant {applicant_data.get('email')} at center {visa_center}.")
                
                runtime_config = self.api.get_runtime_config() or {}
                captcha_config = runtime_config.get("captcha", {})
                
                proxy_string = account.get("proxy_string")
                if proxy_string and not proxy_string.startswith("http"):
                    parts = proxy_string.split(":")
                    if len(parts) == 4:
                        host, port, user, pwd = parts
                        proxy_string = f"http://{user}:{pwd}@{host}:{port}"
                    else:
                        proxy_string = f"http://{proxy_string}"
                if proxy_string and "127.0.0.1" in os.getenv("BOOKING_PORTAL_URL", ""):
                    proxy_string = None
                
                if os.getenv('USE_MOCK_CAPTCHA', 'False').lower() in ['true', '1']:
                    from mock_captcha import MockCaptchaService
                    captcha_svc = MockCaptchaService()
                else:
                    captcha_svc = CapSolverService(api_key=captcha_config.get("api_key", ""), proxy_string=proxy_string)
                
                # Instantiate our new unified GVCAdapter!
                adapter = GVCAdapter(captcha_service=captcha_svc, headless=True, proxy_string=proxy_string)
                
                # Setup session specific to this account
                adapter.cookie_file = f"cookies_{account['id']}.pkl"
                adapter.load_session()
                
                # 5. Execute Booking Flow
                logging.info(f"Logging in to portal for account {account['username']}...")
                try:
                    if adapter.login(account["username"], account["password"]):
                        
                        logging.info("Injecting applicant data...")
                        adapter.inject_applicant_data(applicant_data, visa_center)
                        
                        logging.info("Solving Pre-OTP booking captcha...")
                        if adapter.pass_pre_otp_captcha():
                        
                            logging.info("Triggering OTP generation...")
                            adapter.request_otp()
                            
                            # Polling the SaaS for the OTP code via our new endpoint
                            logging.info("Polling SaaS for intercepted OTP...")
                            otp_code = None
                            for _ in range(24): # 2 minutes max
                                otp_code = self.api.get_booking_task_otp(task_id)
                                if otp_code:
                                    break
                                time.sleep(5)
                                
                            if otp_code:
                                logging.info(f"OTP retrieved: {otp_code}. Finalizing booking...")
                                success = adapter.submit_otp_and_book(otp_code)
                                
                                if success:
                                    self.api.log_event(task_id, "BOOKING_SUCCESS", "info", {"task_id": task_id, "status": "Success"})
                                    # Complete lease
                                    self.api.complete_assignment(task_id)
                                else:
                                    self.api.log_event(task_id, "BOOKING_FAILED", "error", {"reason": "Final submission failed"})
                            else:
                                logging.error("Failed to retrieve OTP from SaaS within timeout.")
                                self.api.log_event(task_id, "BOOKING_FAILED", "error", {"reason": "OTP timeout"})
                        else:
                            self.api.log_event(task_id, "BOOKING_FAILED", "error", {"reason": "Pre-OTP Captcha failed"})
                    else:
                        self.api.log_event(task_id, "LOGIN_FAILED", "error", {"reason": "Failed to login to portal"})
                except Exception as e:
                    logging.error(f"Worker Engine encountered error during booking: {e}")
                    self.api.log_event(task_id, "BOOKING_EXCEPTION", "error", {"error": str(e)})
                finally:
                    # Don't complete the assignment if it failed so it can be retried by another worker
                    pass
                    
                # Short delay before picking up next lease
                time.sleep(5)
                
            except Exception as e:
                logging.error(f"Worker Engine encountered fatal error: {e}")
                time.sleep(10)

if __name__ == '__main__':
    base_url = os.getenv("SAAS_BASE_URL", "http://localhost:8000")
    print(f"Starting Headless Booker Node connecting to {base_url}...")
    
    engine = BookerEngine(base_url)
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)
    
    saas_handler = SaaSStreamHandler(engine.api)
    saas_handler.setFormatter(formatter)
    root_logger.addHandler(saas_handler)
    
    engine.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping booker worker...")
        engine.stop()
