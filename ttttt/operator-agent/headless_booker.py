import time
import logging
import sys
import os
import threading
from dotenv import load_dotenv

from api_client import SaaSClient
from captcha_service import CapSolverService
from core.gvc_adapter import GVCAdapter
from core.browser_persona import BrowserPersonaManager

load_dotenv()

class SaaSStreamHandler(logging.Handler):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
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
    def __init__(self, base_url: str, worker_id: str = None):
        super().__init__(daemon=True)
        self.worker_id = worker_id or os.getenv("WORKER_HOSTNAME", f"booker-{os.getpid()}")
        self.api = SaaSClient(base_url, cred_file=f"booker_{self.worker_id}_creds.txt")
        self._stop_event = threading.Event()
        self.persona = BrowserPersonaManager.get_persona_for_worker(self.worker_id)
        logging.info(f"BookerEngine [{self.worker_id}]: Assigned Browser Persona '{self.persona.persona_id}' (TLS: {self.persona.tls_target})")

    def stop(self):
        self._stop_event.set()

    def run(self):
        logging.info(f"Starting Headless Booker Engine for worker '{self.worker_id}'...")
        
        # Initial jitter delay to stagger worker registration
        self.persona.apply_jitter(multiplier=0.5)
        
        # 1. Register with SaaS as a Booking-capable worker
        registered = False
        for attempt in range(10):
            if self.api.register(hostname=self.worker_id, can_scrape=False, can_book=True):
                registered = True
                break
            logging.info(f"[{self.worker_id}] SaaS not ready yet (Attempt {attempt+1}/10). Retrying in 3 seconds...")
            time.sleep(3)
            
        if not registered:
            logging.error(f"[{self.worker_id}] Failed to register with SaaS after 10 attempts. Cannot start booker.")
            return
            
        # 2. Start Heartbeat thread
        self.api.start_heartbeat()
        
        while not self._stop_event.is_set():
            try:
                # 3. Pull next assignment
                lease, retry_after = self.api.get_next_lease()
                
                if not lease:
                    logging.info(f"[{self.worker_id}] No booking tasks available. Sleeping for {retry_after} seconds.")
                    self._stop_event.wait(retry_after)
                    continue
                    
                if "booking_task_context" not in lease:
                    logging.warning(f"[{self.worker_id}] Received a non-booking lease. Completing it immediately to avoid blocking.")
                    self.api.complete_assignment(lease["lease_id"])
                    continue
                    
                # 4. Parse Booking Lease
                task = lease["booking_task_context"]
                task_id = task["id"]
                account = lease["scraper_account"]
                visa_center = task["visa_center"]
                applicant_data = task["applicant_data"]
                
                # Merge slot payload details (periodslotid, time, date) into applicant data
                slot_payload = task.get("slot_payload") or {}
                if isinstance(slot_payload, dict):
                    applicant_data["periodslotid"] = slot_payload.get("periodslotid") or slot_payload.get("id") or applicant_data.get("periodslotid")
                    applicant_data["target_time"] = slot_payload.get("starttime") or task.get("target_time") or "12:00"
                    applicant_data["target_date"] = task.get("target_date") or slot_payload.get("date") or "12/08/2026"
                
                logging.info(f"[{self.worker_id}] Received Booking Task #{task_id} for applicant {applicant_data.get('email')} (Slot ID: {applicant_data.get('periodslotid')}) at center {visa_center}.")
                
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
                portal_url = os.getenv("BOOKING_PORTAL_URL", "")
                disable_proxies = os.getenv("DISABLE_PROXIES", "false").lower() in ["true", "1"]
                is_custom_portal = bool(portal_url and "gvcworld.eu" not in portal_url)
                use_mock = os.getenv("USE_MOCK_CAPTCHA", "false").lower() in ["true", "1"]
                
                if disable_proxies or is_custom_portal or use_mock or "127.0.0.1" in portal_url or "localhost" in portal_url:
                    proxy_string = None
                
                if os.getenv('USE_MOCK_CAPTCHA', 'False').lower() in ['true', '1']:
                    from mock_captcha import MockCaptchaService
                    captcha_svc = MockCaptchaService()
                else:
                    captcha_svc = CapSolverService(api_key=captcha_config.get("api_key", ""), proxy_string=proxy_string)
                
                # Instantiate polymorphic GVCAdapter
                adapter = GVCAdapter(captcha_service=captcha_svc, headless=True, proxy_string=proxy_string, persona=self.persona)
                
                # Setup session specific to this account
                adapter.cookie_file = f"cookies_{account['id']}.pkl"
                adapter.load_session()
                
                # 5. Execute Booking Flow
                logging.info(f"[{self.worker_id}] Logging in to portal for account {account['username']}...")
                try:
                    from core.gvc_adapter import WAFBlockedException, LoginFailedException, AlreadyBookedException
                except ImportError:
                    WAFBlockedException = type("WAFBlockedException", (Exception,), {})
                    LoginFailedException = type("LoginFailedException", (Exception,), {})
                    AlreadyBookedException = type("AlreadyBookedException", (Exception,), {})
                    
                agent_login_success = False
                try:
                    agent_login_success = adapter.login(account["username"], account["password"])
                except WAFBlockedException as e:
                    logging.warning(f"[{self.worker_id}] Worker Engine hit WAF block during login: {e}")
                    self.api.log_event(task_id, "PROXY_BANNED", "error", {"reason": str(e)})
                    self.api.fail_booking_task(task_id, reason="PROXY_BANNED", details=str(e))
                except LoginFailedException as e:
                    logging.error(f"[{self.worker_id}] Worker Engine login failed due to invalid credentials: {e}")
                    self.api.log_event(task_id, "LOGIN_FAILED", "error", {"reason": str(e)})
                    self.api.fail_booking_task(task_id, reason="LOGIN_FAILED", details=str(e))
                except Exception as e:
                    logging.error(f"[{self.worker_id}] Worker Engine encountered error during booking: {e}")
                    self.api.log_event(task_id, "BOOKING_EXCEPTION", "error", {"error": str(e)})
                    self.api.fail_booking_task(task_id, reason="LOGIN_EXCEPTION", details=str(e))

                try:
                    if agent_login_success:
                        logging.info(f"[{self.worker_id}] Injecting applicant data...")
                        adapter.inject_applicant_data(applicant_data, visa_center)
                        
                        logging.info(f"[{self.worker_id}] Solving Pre-OTP booking captcha...")
                        if adapter.pass_pre_otp_captcha():
                        
                            logging.info(f"[{self.worker_id}] Triggering OTP generation...")
                            adapter.request_otp()
                            
                            # Polling the SaaS for the OTP code via our endpoint
                            logging.info(f"[{self.worker_id}] Polling SaaS for intercepted OTP...")
                            otp_code = None
                            for _ in range(24): # 2 minutes max
                                otp_code = self.api.get_booking_task_otp(task_id)
                                if otp_code:
                                    break
                                if (is_custom_portal or use_mock):
                                    logging.info(f"[{self.worker_id}] Simulator / custom portal detected, auto-supplying test OTP '12345'...")
                                    otp_code = "12345"
                                    break
                                time.sleep(5)
                                
                            if otp_code:
                                logging.info(f"[{self.worker_id}] OTP retrieved: {otp_code}. Finalizing booking...")
                                success = adapter.submit_otp_and_book(otp_code)
                                
                                if success:
                                    logging.info(f"[{self.worker_id}] Booking SUCCESS for Task #{task_id}!")
                                    ref_num = f"GVC-{visa_center}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                                    conf_payload = {
                                        "status": "Confirmed",
                                        "reference_number": ref_num,
                                        "applicant_name": f"{applicant_data.get('firstname', '')} {applicant_data.get('surname', '')}".strip(),
                                        "passport_number": applicant_data.get("passportnumber", ""),
                                        "visa_center": visa_center,
                                        "appointment_date": task.get("target_date", ""),
                                        "appointment_time": task.get("target_time", ""),
                                        "confirmed_at": datetime.now().isoformat()
                                    }
                                    self.api.submit_booking_confirmation(task_id, reference_number=ref_num, confirmation_payload=conf_payload)
                                    self.api.log_event(task_id, "BOOKING_SUCCESS", "info", {"task_id": task_id, "reference_number": ref_num, "status": "Success"})
                                    self.api.complete_assignment(task_id)
                                else:
                                    self.api.log_event(task_id, "BOOKING_FAILED", "error", {"reason": "Final submission failed"})
                                    self.api.fail_booking_task(task_id, reason="Final submission failed")
                            else:
                                logging.error(f"[{self.worker_id}] Failed to retrieve OTP from SaaS within timeout.")
                                self.api.log_event(task_id, "BOOKING_FAILED", "error", {"reason": "OTP timeout"})
                                self.api.fail_booking_task(task_id, reason="OTP_TIMEOUT")
                        else:
                            self.api.log_event(task_id, "BOOKING_FAILED", "error", {"reason": "Pre-OTP Captcha failed"})
                            self.api.fail_booking_task(task_id, reason="CAPTCHA_FAILED")
                    elif not agent_login_success:
                        self.api.fail_booking_task(task_id, reason="LOGIN_FAILED")
                except AlreadyBookedException as abe:
                    logging.warning(f"[{self.worker_id}] Applicant already has active appointment on portal: {abe}")
                    self.api.log_event(task_id, "BOOKING_ALREADY_EXISTS", "warning", {"reason": str(abe)})
                    self.api.fail_booking_task(task_id, reason="ALREADY_BOOKED", details=str(abe))
                except Exception as e:
                    logging.error(f"[{self.worker_id}] Error during post-login booking flow: {e}")
                    self.api.log_event(task_id, "BOOKING_EXCEPTION", "error", {"error": str(e)})
                    self.api.fail_booking_task(task_id, reason="BOOKING_EXCEPTION", details=str(e))
                finally:
                    # Upload captured network traces/HAR to SaaS
                    try:
                        net_logs = adapter.get_network_logs()
                        if net_logs:
                            self.api.submit_network_logs(task.get("assignment_id") or 1, net_logs)
                    except Exception as log_err:
                        logging.warning(f"[{self.worker_id}] Could not submit network logs: {log_err}")
                    
                time.sleep(3)
                
            except Exception as e:
                logging.error(f"[{self.worker_id}] Fatal error: {e}")
                time.sleep(5)

if __name__ == '__main__':
    from datetime import datetime
    from logging.handlers import TimedRotatingFileHandler
    
    base_url = os.getenv("SAAS_BASE_URL", "http://localhost:8000")
    worker_id = os.getenv("WORKER_HOSTNAME", f"booker-{os.getpid()}")
    print(f"Starting Headless Booker Node [{worker_id}] connecting to {base_url}...")
    
    os.makedirs('logs', exist_ok=True)
    engine = BookerEngine(base_url, worker_id=worker_id)
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)
    
    # Daily rotating file handler (7-day retention)
    file_handler = TimedRotatingFileHandler("logs/booker.log", when="midnight", interval=1, backupCount=7, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
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
