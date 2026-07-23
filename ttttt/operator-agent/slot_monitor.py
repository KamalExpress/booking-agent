import time
import logging
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from api_client import SaaSClient

# Using existing main_operator since it handles session, WAF, proxies
from main_operator import OperatorAgent
from captcha_service import CapSolverService

def generate_dates_between(start_str, end_str):
    date_format = "%d/%m/%Y"
    start_date = datetime.strptime(start_str, date_format)
    end_date = datetime.strptime(end_str, date_format)
    delta = end_date - start_date
    return [(start_date + timedelta(days=i)).strftime(date_format) for i in range(delta.days + 1)]

class SlotMonitorEngine(threading.Thread):
    def __init__(self, base_url: str):
        super().__init__(daemon=True)
        self.api = SaaSClient(base_url)
        self._stop_event = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=5)

    def stop(self):
        self._stop_event.set()
        self.executor.shutdown(wait=False)

    def run(self):
        logging.info("Starting Worker Node Scheduler Engine (Parallel Mode)...")
        
        # 1. Register with SaaS (with retries in case FastAPI is still booting)
        registered = False
        for attempt in range(10):
            if self.api.register(hostname="worker-01"):
                registered = True
                break
            logging.info(f"SaaS not ready yet (Attempt {attempt+1}/10). Retrying in 3 seconds...")
            time.sleep(3)
            
        if not registered:
            logging.error("Failed to register with SaaS after 10 attempts. Cannot start worker.")
            return
            
        # 2. Start Heartbeat thread
        self.api.start_heartbeat()
        
        while not self._stop_event.is_set():
            try:
                # 3. Pull next assignment
                lease, retry_after = self.api.get_next_lease()
                
                if not lease:
                    logging.info(f"No assignments available. Sleeping for {retry_after} seconds.")
                    self._stop_event.wait(retry_after)
                    continue
                
                # Dispatch to Thread Pool
                self.executor.submit(self._process_lease, lease)
                
                # Small delay to prevent hammering the pull endpoint too fast
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"Worker Engine loop encountered error: {e}", exc_info=True)
                time.sleep(5)

    def _process_lease(self, lease):
        try:
            # 4. Parse Lease
            assignment_id = lease["assignment_context"]["id"]
            account = lease["scraper_account"]
            visa_center = lease["assignment_context"]["visa_center"]
            date_from = lease["assignment_context"]["date_from"]
            date_to = lease["assignment_context"]["date_to"]
            
            logging.info(f"[Thread] Received Assignment #{assignment_id} for center {visa_center}.")
            
            # Setup Agent using dynamic runtime config
            runtime_config = self.api.get_runtime_config() or {}
            captcha_config = runtime_config.get("captcha", {})
            behavior_config = runtime_config.get("behavior", {})
            min_delay = behavior_config.get("min_slot_delay", 4.0)
            max_delay = behavior_config.get("max_slot_delay", 8.0)
            
            # Setup proxy string
            proxy = lease.get("proxy")
            proxy_string = None
            if proxy:
                if proxy.get("protocol") == "http":
                    proxy_string = f"http://{proxy.get('username', '')}:{proxy.get('password', '')}@{proxy['host']}:{proxy['port']}"
                else:
                    proxy_string = f"{proxy.get('protocol', 'http')}://{proxy['host']}:{proxy['port']}"
            import os
            if account.get("proxy_string"):
                proxy_string = account.get("proxy_string")
                if not proxy_string.startswith("http"):
                    proxy_string = f"http://{proxy_string}"
            
            if "127.0.0.1" in os.getenv("BOOKING_PORTAL_URL", ""):
                proxy_string = None
            
            # Initialize MockCaptchaService if enabled, else CapSolverService
            if os.getenv('USE_MOCK_CAPTCHA', 'False').lower() in ['true', '1']:
                from mock_captcha import MockCaptchaService
                captcha_svc = MockCaptchaService()
            elif captcha_config.get("provider") == "capsolver":
                from captcha_service import CapSolverService
                captcha_svc = CapSolverService(api_key=captcha_config.get("api_key", ""), proxy_string=proxy_string)
            else:
                from captcha_service import CapSolverService
                captcha_svc = CapSolverService(api_key="", proxy_string=proxy_string)
            
            # Instantiate the unified operator agent
            agent = OperatorAgent(captcha_svc, username=account["username"], password=account["password"], proxy_string=proxy_string)
            
            # Make sure the session file matches the account so we don't mix cookies
            agent.cookie_file = f"cookies_{account['id']}.pkl"
            agent.load_session()
            
            # 5. Execute Assignment Logic
            logging.info(f"Executing login flow for account {account['username']}...")
            try:
                login_success = agent.login()
            except Exception as e:
                logging.error(f"Worker Engine encountered error during login: {e}")
                self.api.log_event(assignment_id, "LOGIN_EXCEPTION", "error", {"username": account["username"], "error": str(e)})
                login_success = False
            
            if not login_success:
                self.api.log_event(assignment_id, "LOGIN_FAILED", "error", {"username": account["username"]})
                logging.error("Login failed. Discarding assignment lease.")
                self.api.report_lease_result(assignment_id, "FAILED", "Login failed")
                return
                
            self.api.log_event(assignment_id, "LOGIN_SUCCESS", "info", {"username": account["username"]})
            
            dates_to_check = generate_dates_between(date_from, date_to)
            
            centers_to_check = [c.strip() for c in visa_center.split(",") if c.strip()]
            if not centers_to_check:
                centers_to_check = ["138:26"] # Fallback to Lahore Standard
                
            slots_found = False
            for target_date in dates_to_check:
                if self._stop_event.is_set():
                    break
                    
                for center_str in centers_to_check:
                    if self._stop_event.is_set():
                        break
                        
                    parts = center_str.split(":")
                    vac_id = parts[0]
                    app_type = parts[1] if len(parts) > 1 else "26"
                    
                    logging.info(f"Checking slots for {target_date} at VAC {vac_id} (Type {app_type})...")
                    
                    # --- POC MOCK LOGIC ---
                    date_obj = datetime.strptime(target_date, "%d/%m/%Y")
                    if date_obj.weekday() < 5: # Monday is 0, Sunday is 6. Weekdays are 0-4.
                        logging.info("POC Mock: Injecting 20 mock slots for weekday.")
                        mock_slots = []
                        for i in range(20):
                            mock_slots.append({
                                "isavailable": True,
                                "isselectable": True,
                                "starttime": f"{8 + (i // 4):02d}:{(i % 4) * 15:02d}", # 08:00, 08:15...
                            })
                        slots_response = {
                            "code": "SUCCESS",
                            "returnobject": {"slots": mock_slots}
                        }
                    else:
                        # For weekends, either run normal check or mock empty.
                        # Since it's a POC, let's just mock empty for weekends to save requests.
                        slots_response = {
                            "code": "SUCCESS",
                            "returnobject": {"slots": []}
                        }
                    # --- END POC MOCK LOGIC ---
                    
                    if slots_response and slots_response.get("code") == "SUCCESS":
                        ret_obj = slots_response.get("returnobject")
                        slots = ret_obj.get("slots", []) if isinstance(ret_obj, dict) else (ret_obj if isinstance(ret_obj, list) else [])
                        
                        available = [s for s in slots if s.get('isavailable') and s.get('isselectable')]
                        if available:
                            logging.info(f"Found {len(available)} slots on {target_date} for VAC {vac_id}!")
                            # Use thread-safe logging or rely on API client thread-safety
                            self.api.log_event(assignment_id, "SLOT_FOUND", "info", {
                                "date": target_date,
                                "visa_center": vac_id,
                                "slots": available,
                                "slot_count": len(available)
                            })
                            slots_found = True
                            # Don't break here! We want to check other centers for this date too.
                    elif slots_response and slots_response.get("status_code") == 429:
                        logging.warning("Hit 429 Rate Limit. Pausing slot checks for this run.")
                        self.api.log_event(assignment_id, "RATE_LIMIT_HIT", "warning", {"date": target_date})
                        break
                    
                    # Prevent hammering the API with a human-like randomized delay between checks
                    import random
                    delay = random.uniform(min_delay, max_delay)
                    logging.info(f"Waiting {delay:.2f}s before next check...")
                    self._stop_event.wait(delay)
                    
                if slots_response and slots_response.get("status_code") == 429:
                    break
            
            if not slots_found:
                logging.info("Finished checking assignment date range. No slots found.")
                self.api.log_event(assignment_id, "NO_SLOTS_FOUND", "info", {"date_from": date_from, "date_to": date_to})
            
        except Exception as e:
            logging.error(f"Worker Engine encountered error: {e}", exc_info=True)
            
            # Report exception to SaaS so it's not silent on the dashboard
            try:
                a_id = locals().get('assignment_id', None)
                if a_id:
                    self.api.report_lease_result(a_id, "FAILED", str(e))
                self.api.log_event(a_id, "WORKER_ERROR", "error", {"error": str(e), "traceback": "Check local worker logs for full trace."})
            except Exception as log_e:
                logging.error(f"Failed to push error log to SaaS: {log_e}")
                
        finally:
            # Transmit Network Logs
            if 'agent' in locals() and hasattr(agent, 'get_network_logs'):
                net_logs = agent.get_network_logs()
                if net_logs:
                    a_id = locals().get('assignment_id', None)
                    try:
                        self.api.submit_network_logs(a_id, net_logs)
                        logging.info(f"Transmitted {len(net_logs)} network logs to SaaS.")
                    except Exception as log_e:
                        logging.error(f"Failed to transmit network logs to SaaS: {log_e}")
            
            # If we completed the assignment, mark it complete and wait a tiny bit
            if 'assignment_id' in locals() and assignment_id and 'e' not in locals() and locals().get('login_success', False):
                try:
                    self.api.report_lease_result(assignment_id, "COMPLETED")
                except Exception as comp_e:
                    logging.error(f"Failed to complete assignment: {comp_e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    engine = SlotMonitorEngine("http://127.0.0.1:8000")
    engine.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        engine.stop()