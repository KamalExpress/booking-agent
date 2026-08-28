import time
import logging
import sys
import os
import threading
from dotenv import load_dotenv

from api_client import SaaSClient
from captcha_service import CapSolverService
from core.adapters.adapter_factory import AdapterFactory
import core.adapters.gvc_adapter  # Ensure adapters are registered

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
            if self.api.register(hostname="booker-01", can_scrape=False, can_book=True, supported_providers=["GVC"]):
                registered = True
                # 2. Start Heartbeat thread
                self.api.start_heartbeat()
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
                    
                # 4. Parse Booking Lease Context
                task = lease["booking_task_context"]
                task_id = task["id"]
                account = lease["scraper_account"]
                visa_center = task["visa_center"]
                applicant_data = task["applicant_data"]
                target_date = task.get("target_date")
                target_time = task.get("target_time")
                slot_payload = task.get("slot_payload") or {}
                
                # Step 1: Log Task Claimed
                self.api.log_event(task_id, "BOOKING_CLAIMED", "info", {
                    "task_id": task_id,
                    "applicant_email": applicant_data.get("email"),
                    "applicant_name": f"{applicant_data.get('firstname')} {applicant_data.get('surname')}",
                    "visa_center": visa_center,
                    "target_date": target_date,
                    "target_time": target_time,
                    "account_username": account.get("username")
                })
                logging.info(f"Claimed Booking Task #{task_id} for applicant {applicant_data.get('email')} at center {visa_center} ({target_date} {target_time}).")
                
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
                
                # Instantiate the correct adapter dynamically
                provider = task.get("provider", "GVC").upper()
                adapter = AdapterFactory.get_adapter(provider, captcha_service=captcha_svc, headless=True, proxy_string=proxy_string)
                
                # Setup session specific to this account
                adapter.cookie_file = f"cookies_{account['id']}.pkl"
                adapter.load_session()
                
                # Step 2: Login to Portal
                self.api.log_event(task_id, "BOOKING_LOGIN_START", "info", {"account": account["username"], "provider": provider})
                logging.info(f"Logging in to portal for account {account['username']}...")
                try:
                    from core.adapters.gvc_adapter import WAFBlockedException, LoginFailedException
                except ImportError:
                    WAFBlockedException = type("WAFBlockedException", (Exception,), {})
                    LoginFailedException = type("LoginFailedException", (Exception,), {})
                    
                agent_login_success = False
                try:
                    agent_login_success = adapter.login(account["username"], account["password"])
                except WAFBlockedException as e:
                    logging.warning(f"Worker Engine hit WAF block during login: {e}")
                    self.api.log_event(task_id, "BOOKING_FAILED", "error", {"step": "LOGIN", "reason": "WAF Blocked", "error": str(e)})
                    self.api.log_event(task_id, "PROXY_BANNED", "error", {"reason": str(e)})
                except LoginFailedException as e:
                    logging.error(f"Worker Engine login failed due to invalid credentials: {e}")
                    self.api.log_event(task_id, "BOOKING_FAILED", "error", {"step": "LOGIN", "reason": "Invalid Credentials", "error": str(e)})
                    self.api.log_event(task_id, "LOGIN_FAILED", "error", {"reason": str(e)})
                except Exception as e:
                    logging.error(f"Worker Engine encountered error during login: {e}")
                    self.api.log_event(task_id, "BOOKING_FAILED", "error", {"step": "LOGIN", "reason": "Exception", "error": str(e)})

                try:
                    if agent_login_success:
                        self.api.log_event(task_id, "BOOKING_LOGIN_SUCCESS", "info", {"account": account["username"]})
                        
                        # Step 3: Inject Applicant Data & Bind Slot Selection
                        applicant_data["slot_id"] = slot_payload.get("id") or applicant_data.get("slot_id")
                        applicant_data["target_date"] = target_date
                        applicant_data["target_time"] = target_time
                        logging.info(f"Injecting applicant data and binding Slot ID {applicant_data.get('slot_id')} ({target_date} {target_time})...")
                        adapter.inject_applicant_data(applicant_data, visa_center)
                        self.api.log_event(task_id, "BOOKING_DATA_INJECTED", "info", {
                            "passport": applicant_data.get("passportnumber"),
                            "name": f"{applicant_data.get('firstname')} {applicant_data.get('surname')}",
                            "dob": applicant_data.get("dateofbirth"),
                            "slot_id": applicant_data.get("slot_id")
                        })
                        self.api.log_event(task_id, "BOOKING_SLOT_SELECTED", "info", {
                            "slot_id": applicant_data.get("slot_id"),
                            "target_date": target_date,
                            "target_time": target_time,
                            "visa_center": visa_center
                        })
                        
                        # Step 4: Solve Pre-OTP Booking Captcha
                        self.api.log_event(task_id, "BOOKING_CAPTCHA_START", "info", {"stage": "pre_otp"})
                        logging.info("Solving Pre-OTP booking captcha...")
                        if adapter.pass_pre_otp_captcha():
                            self.api.log_event(task_id, "BOOKING_CAPTCHA_SUCCESS", "info", {"stage": "pre_otp"})
                        
                            # Step 5: Trigger OTP Generation
                            self.api.log_event(task_id, "BOOKING_OTP_REQUESTED", "info", {"phone": applicant_data.get("phone_number")})
                            logging.info("Triggering OTP generation on portal...")
                            otp_triggered = adapter.request_otp()
                            
                            if not otp_triggered:
                                self.api.log_event(task_id, "BOOKING_FAILED", "error", {"step": "OTP_REQUEST", "reason": "Portal rejected OTP request"})
                            else:
                                # Step 6: Poll SaaS for Intercepted OTP
                                self.api.log_event(task_id, "BOOKING_OTP_POLLING", "info", {"timeout_seconds": 120})
                                logging.info("Polling SaaS for intercepted OTP...")
                                otp_code = None
                                for _ in range(24): # 2 minutes max
                                    otp_code = self.api.get_booking_task_otp(task_id)
                                    if otp_code:
                                        break
                                    time.sleep(5)
                                    
                                if otp_code:
                                    self.api.log_event(task_id, "BOOKING_OTP_RECEIVED", "info", {"otp_code": otp_code})
                                    logging.info(f"OTP retrieved: {otp_code}. Finalizing booking submission...")
                                    
                                    # Step 7: Final Submission
                                    self.api.log_event(task_id, "BOOKING_SUBMITTING", "info", {"slot_id": applicant_data.get("slot_id")})
                                    success, result_meta = adapter.submit_otp_and_book(otp_code, task_id=task_id)
                                    
                                    if success:
                                        ref_num = result_meta.get("reference_number", "CONFIRMED")
                                        screenshot = result_meta.get("screenshot_path")
                                        logging.info(f"BOOKING CONFIRMED! Ref: {ref_num}, Screenshot: {screenshot}")
                                        
                                        self.api.log_event(task_id, "BOOKING_SUCCESS", "info", {
                                            "task_id": task_id,
                                            "status": "Success",
                                            "reference_number": ref_num,
                                            "confirmation": result_meta.get("confirmation"),
                                            "screenshot_path": screenshot
                                        })
                                        # Complete lease
                                        self.api.complete_assignment(task_id)
                                    else:
                                        fail_reason = result_meta.get("reason", "Final submission failed")
                                        self.api.log_event(task_id, "BOOKING_FAILED", "error", {"step": "FINAL_SUBMISSION", "reason": fail_reason})
                                else:
                                    logging.error("Failed to retrieve OTP from SaaS within timeout.")
                                    self.api.log_event(task_id, "BOOKING_FAILED", "error", {"step": "OTP_TIMEOUT", "reason": "OTP was not received within 120s"})
                        else:
                            self.api.log_event(task_id, "BOOKING_FAILED", "error", {"step": "CAPTCHA", "reason": "Pre-OTP Captcha failed"})
                except Exception as e:
                    import traceback
                    tb_str = traceback.format_exc()
                    logging.error(f"Worker Engine encountered runtime exception: {e}\n{tb_str}")
                    self.api.log_event(task_id, "BOOKING_FAILED", "error", {
                        "step": "RUNTIME_EXCEPTION",
                        "error": str(e),
                        "traceback": tb_str[:1500]
                    })
                    # Explicitly fail the lease so the task can be immediately retried
                    try:
                        self.api.fail_assignment(task_id)
                    except Exception:
                        pass
                finally:
                    pass
                    
                # Short delay before picking up next lease
                time.sleep(3)
                
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
