import time
import logging
import threading
from datetime import datetime, timedelta
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

    def stop(self):
        self._stop_event.set()

    def run(self):
        logging.info("Starting Worker Node Scheduler Engine...")
        
        # 1. Register with SaaS
        if not self.api.register(hostname="worker-01"):
            logging.error("Failed to register with SaaS. Cannot start worker.")
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
                    
                # 4. Parse Lease
                assignment_id = lease["assignment_context"]["id"]
                account = lease["scraper_account"]
                visa_center = lease["assignment_context"]["visa_center"]
                date_from = lease["assignment_context"]["date_from"]
                date_to = lease["assignment_context"]["date_to"]
                
                logging.info(f"Received Assignment #{assignment_id} for center {visa_center}.")
                
                # Setup Agent using dynamic runtime config
                runtime_config = self.api.get_runtime_config() or {}
                captcha_config = runtime_config.get("captcha", {})
                
                if captcha_config.get("provider") == "capsolver":
                    captcha_svc = CapSolverService(api_key=captcha_config.get("api_key", ""))
                else:
                    # Fallback or manual service could be instantiated here
                    captcha_svc = CapSolverService(api_key="")
                    
                agent = OperatorAgent(captcha_svc, username=account["username"], password=account["password"])
                
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
                    # Sleep briefly and then continue to fetch another
                    self._stop_event.wait(5)
                    continue
                    
                self.api.log_event(assignment_id, "LOGIN_SUCCESS", "info", {"username": account["username"]})
                
                dates_to_check = generate_dates_between(date_from, date_to)
                
                slots_found = False
                for target_date in dates_to_check:
                    if self._stop_event.is_set():
                        break
                        
                    logging.info(f"Checking slots for {target_date}...")
                    slots_response = agent.search_slots(target_date, "26", visa_center)
                    
                    if slots_response and slots_response.get("code") == "SUCCESS":
                        ret_obj = slots_response.get("returnobject")
                        slots = ret_obj.get("slots", []) if isinstance(ret_obj, dict) else (ret_obj if isinstance(ret_obj, list) else [])
                        
                        available = [s for s in slots if s.get('isavailable') and s.get('isselectable')]
                        if available:
                            logging.info(f"Found {len(available)} slots on {target_date}!")
                            self.api.log_event(assignment_id, "SLOT_FOUND", "info", {
                                "date": target_date,
                                "slots": available
                            })
                            slots_found = True
                            break # Just alert once per cycle to avoid spam
                    
                    # Prevent hammering the API
                    self._stop_event.wait(1.5)
                
                if not slots_found:
                    logging.info("Finished checking assignment date range. No slots found.")
                
            except Exception as e:
                logging.error(f"Worker Engine encountered error: {e}", exc_info=True)
                
                # Report exception to SaaS so it's not silent on the dashboard
                try:
                    # assignment_id might not be bound if exception happened early, default to None
                    a_id = locals().get('assignment_id', None)
                    self.api.log_event(a_id, "WORKER_ERROR", "error", {"error": str(e), "traceback": "Check local worker logs for full trace."})
                except Exception as log_e:
                    logging.error(f"Failed to push error log to SaaS: {log_e}")
                
            # If we completed the assignment, mark it complete and wait a tiny bit
            if 'assignment_id' in locals() and assignment_id:
                try:
                    self.api.complete_assignment(assignment_id)
                except Exception as comp_e:
                    logging.error(f"Failed to complete assignment: {comp_e}")
                    
            self._stop_event.wait(1)
            
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    engine = SlotMonitorEngine("http://127.0.0.1:8000")
    engine.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        engine.stop()