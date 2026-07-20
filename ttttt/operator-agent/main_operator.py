import os
import time
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from captcha_service import CaptchaService, NopeChaService
from mock_captcha import MockCaptchaService
from otp_service import OTPService

load_dotenv()

import sys
os.makedirs('logs', exist_ok=True)
log_filename = f"logs/runlog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure logging to write to both the file and the console
handlers = [logging.FileHandler(log_filename, mode='a', encoding='utf-8')]
if sys.stderr is not None and sys.stdout is not None:
    handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=handlers,
    force=True
)

class OperatorAgent:
    def __init__(self, captcha_service: CaptchaService, username: str = None, password: str = None, proxy_string: str = None):
        self.proxy_string = proxy_string
        try:
            from curl_cffi import requests as c_requests
            self.session = c_requests.Session(impersonate="chrome120")
            logging.info("Using curl_cffi Chrome impersonation to bypass WAF.")
        except ImportError:
            self.session = requests.Session()
            logging.warning("curl_cffi not found. Using standard requests (may trigger WAF).")
            
            # Fallback retry logic for standard requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)
        
        if proxy_string:
            self.session.proxies = {
                "http": proxy_string,
                "https": proxy_string
            }
        
        # Standardize headers to match Playwright context and bypass anti-bot
        # Do NOT override User-Agent, let curl_cffi match the TLS fingerprint precisely
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Origin": "https://pk-gr-services.gvcworld.eu",
            "Referer": "https://pk-gr-services.gvcworld.eu/?lang=en_US",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        })
        
        self.username = username or os.getenv('GVC_USERNAME')
        self.password = password or os.getenv('GVC_PASSWORD')
        self.base_url = "https://pk-gr-services.gvcworld.eu"
        self.sitekey = os.getenv('TARGET_SITEKEY', '6LcnlCoUAAAAAJLjWXXaByTFyuOLf4K0gGu5r3d2')
        self.captcha_service = captcha_service
        
        otp_endpoint = os.getenv('OTP_API_ENDPOINT')
        otp_key = os.getenv('OTP_API_KEY')
        self.otp_service = OTPService(api_endpoint=otp_endpoint, api_key=otp_key) if otp_endpoint else None
        
        self.cookie_file = "last-login-token.pkl"
        self.load_session()
        
        # Monkey-patch session.request to intercept network logs
        self.network_logs = []
        original_request = self.session.request
        
        def intercepted_request(method, url, *args, **kwargs):
            req_time = datetime.utcnow()
            try:
                response = original_request(method, url, *args, **kwargs)
                res_time = datetime.utcnow()
                
                req_body = kwargs.get('json') or kwargs.get('data') or ""
                if isinstance(req_body, dict):
                    import json
                    req_body = json.dumps(req_body)
                    
                log_entry = {
                    "startedDateTime": req_time.isoformat() + "Z",
                    "time": (res_time - req_time).total_seconds() * 1000,
                    "request": {
                        "method": method.upper(),
                        "url": url,
                        "headers": dict(response.request.headers) if hasattr(response, 'request') else kwargs.get('headers', dict(self.session.headers)),
                        "body": str(req_body)
                    },
                    "response": {
                        "status": response.status_code,
                        "headers": dict(response.headers),
                        "body": response.text[:5000] # Truncate to 5000 chars to avoid massive DB bloat
                    }
                }
                self.network_logs.append(log_entry)
                return response
            except Exception as e:
                log_entry = {
                    "startedDateTime": req_time.isoformat() + "Z",
                    "request": {
                        "method": method.upper(),
                        "url": url,
                        "headers": kwargs.get('headers', dict(self.session.headers)),
                    },
                    "error": str(e)
                }
                self.network_logs.append(log_entry)
                raise
                
        self.session.request = intercepted_request

    def get_network_logs(self):
        return self.network_logs

    def load_session(self):
        import json
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookies_dict = json.load(f)
                    self.session.cookies.update(cookies_dict)
                logging.info("Loaded previous session cookies from file.")
            except Exception as e:
                logging.warning(f"Could not load previous session: {e}")

    def save_session(self):
        import json
        try:
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(self.session.cookies.get_dict(), f)
            logging.info("Saved session cookies to file for future runs.")
        except Exception as e:
            logging.warning(f"Could not save session: {e}")

    def clear_session(self):
        self.session.cookies.clear()
        if os.path.exists(self.cookie_file):
            try:
                os.remove(self.cookie_file)
                logging.info("Cleared expired session cookies file.")
            except Exception:
                pass

    def refresh_waf_cookies(self):
        """
        Headless Playwright flow to quickly execute Imperva JS challenge and extract fresh cookies.
        """
        logging.warning("Refreshing WAF cookies via Headless Playwright...")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logging.error("Playwright is not installed. Cannot refresh WAF cookies.")
            return False

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                
                context_kwargs = {
                    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "viewport": {'width': 1280, 'height': 720},
                    "extra_http_headers": {
                        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"macOS"'
                    }
                }
                
                if hasattr(self, 'proxy_string') and self.proxy_string:
                    from urllib.parse import urlparse
                    parsed = urlparse(self.proxy_string)
                    if parsed.hostname:
                        proxy_conf = {"server": f"http://{parsed.hostname}:{parsed.port}"}
                        if parsed.username:
                            proxy_conf["username"] = parsed.username
                            proxy_conf["password"] = parsed.password
                        context_kwargs["proxy"] = proxy_conf

                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                
                try:
                    from playwright_stealth import Stealth
                    Stealth().apply_stealth_sync(page)
                except ImportError:
                    try:
                        from playwright_stealth import stealth_sync
                        stealth_sync(page)
                    except ImportError:
                        logging.warning("playwright_stealth not found, WAF might still detect headless.")
                
                # Navigate to the login page (without networkidle, as tracking scripts can prevent it)
                logging.info(f"Navigating to {self.base_url}/login to clear WAF...")
                # Use wait_until="commit" so Playwright doesn't wait for the extremely slow WAF assets to fully 'load'
                page.goto(f"{self.base_url}/login", wait_until="commit", timeout=60000)
                
                # Wait for the username input box to appear. This guarantees Imperva has fully cleared us.
                logging.info("Waiting for Imperva JS challenge to clear and login form to render...")
                username_selector = 'input[name="username"], input[type="email"], input[id*="user"]'
                # Allow up to 90 seconds for the WAF challenge to compute on the slow VPS proxy
                page.wait_for_selector(username_selector, timeout=90000)
                logging.info("Login form detected! WAF challenge successfully bypassed.")
                
                # Extract and inject cookies
                cookies = context.cookies()
                self.session.cookies.clear() # Completely wipe the old tainted cookie jar
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', 'pk-gr-services.gvcworld.eu'))
                    
                logging.info(f"Successfully refreshed {len(cookies)} WAF cookies.")
                self.save_session()
                return True
        except Exception as e:
            logging.error(f"Failed to refresh WAF cookies via Playwright: {e}")
            return False

    def is_authenticated(self):
        """
        Lightweight check to see if the loaded session cookies are still valid.
        This prevents burning CapSolver credits if we already have a valid session.
        """
        try:
            logging.info("Validating existing session...")
            url = f"{self.base_url}/api/v1/periodslot/slots"
            # Dummy payload just to check authentication state
            payload = {
                "datefrom": "01/01/2026", "type": 26, "bookingfor": 0, "members": 1, "method": 1,
                "travelpurposes": -1, "howmanyapplicantsareunder12": 0, "appointmentId": "undefined",
                "id": 0, "vac": {"id": 138}
            }
            
            for attempt in range(2):
                response = self.session.put(url, json=payload, timeout=15)
                if response.status_code == 200:
                    logging.info("Session is fully valid. Bypassing login.")
                    return True
                elif response.status_code == 401:
                    logging.info("Session has expired (401). Must login again.")
                    return False
                elif response.status_code in [403, 502, 503, 504, 522]:
                    logging.warning(f"Session check hit WAF block ({response.status_code}). Refreshing WAF cookies...")
                    self.refresh_waf_cookies()
                    continue
                else:
                    return False
            return False
        except Exception as e:
            logging.warning(f"Session validation error: {e}")
            # If timeout/WAF drop, try to refresh WAF once
            if "28" in str(e) or "timeout" in str(e).lower():
                self.refresh_waf_cookies()
                try:
                    response = self.session.put(url, json=payload, timeout=15)
                    if response.status_code == 200:
                        return True
                except:
                    pass
            return False

    def login(self):
        if self.is_authenticated():
            return True
            
        logging.info(f"Attempting login for {self.username}...")
        
        # 1. PRE-FLIGHT NAVIGATION: Establish Incapsula TLS Fingerprint & Session Cookies
        logging.info("Executing pre-flight navigation to establish WAF trust...")
        try:
            # We explicitly override the API fetch headers to standard document navigation headers for this single request
            preflight_headers = {
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "X-Requested-With": None # Remove X-Requested-With for the document request
            }
            self.session.get(f"{self.base_url}/?lang=en_US", headers=preflight_headers, timeout=15)
        except Exception as e:
            logging.warning(f"Pre-flight navigation failed (WAF might still block us): {e}")

        # 2. Solve CAPTCHA
        captcha_token = self.captcha_service.solve(self.sitekey, f"{self.base_url}/login", session=self.session)
        
        # Intelligent fallback to Manual mode if Auto mode fails
        if not captcha_token and self.captcha_service.__class__.__name__ in ['NopeChaService', 'CapSolverService']:
            logging.warning(f"{self.captcha_service.__class__.__name__} failed! Falling back to Manual Browser Captcha...")
            from captcha_service import ManualCaptchaService
            manual_svc = ManualCaptchaService()
            captcha_token = manual_svc.solve(self.sitekey, f"{self.base_url}/login", session=self.session)
        
        url = f"{self.base_url}/api/v1/auth/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "g-recaptcha-response": captcha_token
        }
        
        logging.debug(f"Login payload: {payload}")
        
        # Consume any dead keep-alive connection resulting from the Captcha wait
        try:
            self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
        except Exception:
            pass
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, json=payload, timeout=30)
                logging.debug(f"Login response status: {response.status_code}, text: {response.text}")
                
                if response.status_code == 200:
                    logging.info("Login successful!")
                    self.save_session()
                    return True
                elif response.status_code in [403, 502, 503, 504, 522]:
                    logging.warning(f"Received {response.status_code} during login. Retrying... ({attempt+1}/{max_retries})")
                    if response.status_code == 403:
                        self.refresh_waf_cookies()
                        try:
                            self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
                        except Exception:
                            pass
                    time.sleep(3)
                    continue
                else:
                    logging.error(f"Login failed. Status Code: {response.status_code}")
                    logging.error(f"Response: {response.text}")
                    return False
                    
            except Exception as e:
                logging.error(f"Network error during login request (Attempt {attempt+1}/{max_retries}): {e}")
                
                # If it's a timeout (28), it usually means WAF tarpitting due to expired cookies
                if "28" in str(e) or "timeout" in str(e).lower():
                    self.refresh_waf_cookies()
                    try:
                        self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
                    except Exception:
                        pass
                    
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return False
                
        return False

    def search_slots(self, date_from, app_type, vac_id):
        url = f"{self.base_url}/api/v1/periodslot/slots"
        logging.info(f"Searching for slots from {date_from}... Endpoint: {url}")
        
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
        
        logging.info(f"Form Data (Payload) sent: {payload}")
        
        logging.debug(f"Search slots payload: {payload}")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.put(url, json=payload, timeout=30)
                logging.debug(f"Search slots response status: {response.status_code}, text: {response.text}")
                
                if response.status_code == 200:
                    slots = response.json()
                    logging.info(f"Slots retrieved successfully from {url}: {slots}")
                    return slots
                elif response.status_code in [403, 502, 503, 504, 522]:
                    logging.warning(f"Received {response.status_code} during search_slots. Retrying... ({attempt+1}/{max_retries})")
                    if response.status_code == 403:
                        self.refresh_waf_cookies()
                    time.sleep(3)
                    continue
                else:
                    logging.error(f"Failed to search slots. Status Code: {response.status_code}")
                    logging.error(f"Response: {response.text}")
                    return {"error": True, "status_code": response.status_code, "text": response.text}
            except Exception as e:
                logging.error(f"Network or WAF Error during search_slots (Attempt {attempt+1}/{max_retries}): {e}")
                
                if "28" in str(e) or "timeout" in str(e).lower():
                    self.refresh_waf_cookies()
                    
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return {"error": True, "status_code": 0, "text": str(e)}
                
        return {"error": True, "status_code": 0, "text": "Max retries exceeded"}

    def request_otp(self, phone_number):
        """
        Placeholder for the API call to tell the portal to generate and send an OTP.
        Once the portal sends the OTP, we poll the custom DB API to retrieve it.
        """
        logging.info("Requesting SMS OTP from portal...")
        # Note: The actual API call to the portal to trigger the SMS is missing from the HAR file.
        # url = f"{self.base_url}/api/v1/otp/send"
        # self.session.post(url, json={"phone": phone_number})
        
        logging.info("SMS OTP requested. Polling database for the received OTP...")
        otp = self.otp_service.fetch_otp(phone_number)
        
        if not otp:
            logging.error("Failed to automatically retrieve OTP. Please ensure the service is running.")
            
        return otp

    def book_appointment(self, slot_details, otp, applicant_data=None):
        """
        Final booking API call using application/x-www-form-urlencoded format.
        """
        logging.info("Submitting final booking request...")
        
        captcha_token = self.captcha_service.solve(self.sitekey, f"{self.base_url}/appointments/add", session=self.session)
        
        # We will assume standard form submission endpoint or API endpoint
        url = f"{self.base_url}/appointments/add"
        
        payload = {
            "vac": os.getenv('APPOINTMENT_VAC_ID', '138'),
            "type": os.getenv('APPOINTMENT_TYPE', '26'),
            "bookingfor": os.getenv('BOOKING_FOR', '0'),
            "otp": otp,
            "g-recaptcha-response": captcha_token
        }
        
        if applicant_data:
            payload.update(applicant_data)
            
        if slot_details and "id" in slot_details:
             payload["periodslot"] = slot_details["id"]
            
        logging.debug(f"Book appointment payload: {payload}")
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        # Consume any dead keep-alive connection resulting from the booking Captcha wait
        try:
            self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
        except Exception:
            pass
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, data=payload, headers=headers, timeout=30)
                logging.debug(f"Book appointment response status: {response.status_code}, text: {response.text}")
                
                if response.status_code == 200:
                    logging.info("Booking confirmed!")
                    return True
                elif response.status_code in [403, 502, 503, 504, 522]:
                    logging.warning(f"Received {response.status_code} during booking. Retrying... ({attempt+1}/{max_retries})")
                    if response.status_code == 403:
                        self.refresh_waf_cookies()
                    time.sleep(3)
                    continue
                else:
                    logging.error(f"Booking failed. Status Code: {response.status_code}")
                    logging.error(f"Response: {response.text}")
                    return False
                    
            except Exception as e:
                logging.error(f"Network error during booking request (Attempt {attempt+1}/{max_retries}): {e}")
                
                if "28" in str(e) or "timeout" in str(e).lower():
                    self.refresh_waf_cookies()
                    
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return False
                
        return False

def main():
    strategy = os.getenv('CAPTCHA_STRATEGY', 'AUTO').upper()
    
    if strategy == 'MOCK' or os.getenv('USE_MOCK_CAPTCHA', 'False').lower() in ['true', '1']:
        logging.info("Using Mock Captcha Service for local demo.")
        captcha_svc = MockCaptchaService()
    elif strategy == 'MANUAL':
        from captcha_service import ManualCaptchaService
        logging.info("Using Manual Browser Captcha Service.")
        captcha_svc = ManualCaptchaService()
    else:
        nopecha_key = os.getenv('NOPECHA_API_KEY')
        if not nopecha_key:
            logging.error("NOPECHA_API_KEY not found in environment. Please setup .env file.")
            return
        captcha_svc = NopeChaService(nopecha_key)
        
    agent = OperatorAgent(captcha_service=captcha_svc)
    
    if not agent.username or not agent.password:
        logging.error("Credentials not found in environment. Please setup .env file.")
        return
        
    if agent.login():
        # Retrieve test parameters from environment or use defaults
        date_from = os.getenv('APPOINTMENT_DATE_FROM', '09/07/2026')
        app_type = os.getenv('APPOINTMENT_TYPE', '26')
        vac_id = os.getenv('APPOINTMENT_VAC_ID', '138')
        
        slots_response = agent.search_slots(date_from, app_type, vac_id)
        
        if slots_response and slots_response.get("code") == "SUCCESS":
            # Dynamically parse the authentic mock API slots and pick the first available one
            slots = slots_response.get("returnobject", {}).get("slots", [])
            selected_slot = None
            for slot in slots:
                if slot.get('isavailable') and slot.get('isselectable'):
                    selected_slot = {"id": slot['id'], "time": slot['starttime'], "date": date_from}
                    break
                    
            if not selected_slot:
                logging.error("No available slots found for booking.")
                return
                
            logging.info(f"Selected available slot: {selected_slot}")
            
            # Fetch applicants from internal portal API
            internal_portal = os.getenv('INTERNAL_PORTAL_URL', 'http://localhost:5001')
            applicants_url = f"{internal_portal}/get-applicants"
            try:
                logging.info(f"Fetching applicant data from {applicants_url}...")
                apps_response = requests.get(applicants_url).json()
                if apps_response and len(apps_response) > 0:
                    internal_app = apps_response[0] # Grab first one for demo
                    phone_number = internal_app.get('phone')
                    
                    otp = agent.request_otp(phone_number)
                    
                    if otp:
                        applicant_data = {
                            "email": internal_app.get('email'),
                            "phonenumberprefix[id]": internal_app.get('phone_prefix_id'),
                            "phonenumber": internal_app.get('phone'),
                            "applicants[][surname]": internal_app.get('surname'),
                            "applicants[][firstname]": internal_app.get('firstname'),
                            "applicants[][dateofbirth]": internal_app.get('dob'),
                            "applicants[][passportnumber]": internal_app.get('passport'),
                            "applicants[][traveldocumentvaliduntil]": internal_app.get('passport_exp'),
                            "applicants[][gender[id]]": internal_app.get('gender_id'),
                            "applicants[][nationality[id]]]": internal_app.get('nationality_id')
                        }
                        agent.book_appointment(selected_slot, otp, applicant_data)
                else:
                    logging.error("No applicants found in internal DB.")
            except Exception as e:
                logging.error(f"Failed to fetch applicants from {applicants_url}: {e}")

if __name__ == "__main__":
    main()
