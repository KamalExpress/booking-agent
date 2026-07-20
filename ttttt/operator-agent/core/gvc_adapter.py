import logging
import time
import os
import json
from core.portal_adapter import BasePortalAdapter
from captcha_service import CaptchaService

class GVCAdapter(BasePortalAdapter):
    def __init__(self, captcha_service: CaptchaService, headless: bool = True, proxy_string: str = None):
        super().__init__(headless)
        self.proxy_string = proxy_string
        try:
            from curl_cffi import requests as c_requests
            self.session = c_requests.Session(impersonate="chrome120")
            logging.info("GVCAdapter: Using curl_cffi Chrome impersonation.")
        except ImportError:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            self.session = requests.Session()
            logging.warning("GVCAdapter: curl_cffi not found. Using standard requests.")
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
            self.session.proxies = {"http": proxy_string, "https": proxy_string}
            
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
        
        self.base_url = "https://pk-gr-services.gvcworld.eu"
        self.sitekey = os.getenv('TARGET_SITEKEY', '6LcnlCoUAAAAAJLjWXXaByTFyuOLf4K0gGu5r3d2')
        self.captcha_service = captcha_service
        self.applicant_data_cache = {}
        self.visa_center_cache = None
        
        self.cookie_file = "gvc-booker-session.pkl"
        self.load_session()

    def load_session(self):
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookies_dict = json.load(f)
                    self.session.cookies.update(cookies_dict)
                logging.info("GVCAdapter: Loaded previous session cookies.")
            except Exception as e:
                logging.warning(f"GVCAdapter: Could not load previous session: {e}")

    def save_session(self):
        try:
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(self.session.cookies.get_dict(), f)
            logging.info("GVCAdapter: Saved session cookies.")
        except Exception as e:
            logging.warning(f"GVCAdapter: Could not save session: {e}")

    def refresh_waf_cookies(self):
        logging.warning("GVCAdapter: Refreshing WAF cookies via Headless Playwright...")
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
                
                if self.proxy_string:
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
                    pass
                
                logging.info(f"GVCAdapter: Navigating to {self.base_url}/login to clear WAF...")
                page.goto(f"{self.base_url}/login", wait_until="commit", timeout=60000)
                
                logging.info("GVCAdapter: Waiting for Imperva JS challenge to clear...")
                username_selector = 'input[name="username"], input[type="email"], input[id*="user"]'
                page.wait_for_selector(username_selector, timeout=90000)
                logging.info("GVCAdapter: WAF challenge successfully bypassed.")
                
                cookies = context.cookies()
                self.session.cookies.clear()
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', 'pk-gr-services.gvcworld.eu'))
                    
                logging.info(f"GVCAdapter: Successfully refreshed {len(cookies)} WAF cookies.")
                self.save_session()
                return True
        except Exception as e:
            logging.error(f"GVCAdapter: Failed to refresh WAF cookies via Playwright: {e}")
            return False

    def is_authenticated(self):
        logging.info("GVCAdapter: Validating existing session...")
        url = f"{self.base_url}/api/v1/periodslot/slots"
        payload = {
            "datefrom": "01/01/2026", "type": 26, "bookingfor": 0, "members": 1, "method": 1,
            "travelpurposes": -1, "howmanyapplicantsareunder12": 0, "appointmentId": "undefined",
            "id": 0, "vac": {"id": 138}
        }
        
        for attempt in range(2):
            try:
                response = self.session.put(url, json=payload, timeout=15)
                if response.status_code == 200:
                    logging.info("GVCAdapter: Session is fully valid.")
                    return True
                elif response.status_code == 401:
                    logging.info("GVCAdapter: Session has expired (401).")
                    return False
                elif response.status_code in [403, 502, 503, 504, 522]:
                    logging.warning(f"GVCAdapter: Session check hit WAF block ({response.status_code}).")
                    self.refresh_waf_cookies()
                    continue
                else:
                    return False
            except Exception as e:
                if attempt == 0:
                    try:
                        self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
                    except:
                        pass
                    continue
                
                if "28" in str(e) or "timeout" in str(e).lower():
                    self.refresh_waf_cookies()
                    try:
                        response = self.session.put(url, json=payload, timeout=15)
                        if response.status_code == 200:
                            return True
                    except:
                        pass
                return False
        return False

    def login(self, username: str, password: str) -> bool:
        if self.is_authenticated():
            return True
            
        logging.info(f"GVCAdapter: Attempting login for {username}...")
        try:
            preflight_headers = {
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "X-Requested-With": None
            }
            self.session.get(f"{self.base_url}/?lang=en_US", headers=preflight_headers, timeout=15)
        except Exception as e:
            logging.warning(f"GVCAdapter: Pre-flight navigation failed: {e}")

        captcha_token = self.captcha_service.solve(self.sitekey, f"{self.base_url}/login", session=self.session)
        if not captcha_token:
            logging.error("GVCAdapter: Failed to solve login captcha.")
            return False

        url = f"{self.base_url}/api/v1/auth/login"
        payload = {"username": username, "password": password, "g-recaptcha-response": captcha_token}
        
        try:
            self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
        except:
            pass
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    logging.info("GVCAdapter: Login successful!")
                    self.save_session()
                    return True
                elif response.status_code in [403, 502, 503, 504, 522]:
                    logging.warning(f"GVCAdapter: Received {response.status_code} during login. Retrying...")
                    if response.status_code == 403:
                        self.refresh_waf_cookies()
                        try:
                            self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
                        except:
                            pass
                    time.sleep(3)
                    continue
                else:
                    logging.error(f"GVCAdapter: Login failed. Status: {response.status_code}")
                    return False
            except Exception as e:
                logging.error(f"GVCAdapter: Network error during login: {e}")
                if "28" in str(e) or "timeout" in str(e).lower():
                    self.refresh_waf_cookies()
                    try:
                        self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
                    except:
                        pass
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return False
        return False

    def inject_applicant_data(self, applicant_data: dict, visa_center: str) -> bool:
        logging.info("GVCAdapter: Caching applicant data for final injection.")
        self.applicant_data_cache = applicant_data
        self.visa_center_cache = visa_center
        return True

    def pass_pre_otp_captcha(self) -> bool:
        logging.info("GVCAdapter: Solving pre-OTP / final booking captcha...")
        self.booking_captcha_token = self.captcha_service.solve(self.sitekey, f"{self.base_url}/appointments/add", session=self.session)
        return bool(self.booking_captcha_token)

    def request_otp(self) -> bool:
        logging.info("GVCAdapter: Triggering OTP via API...")
        # Placeholder for actual OTP trigger request if required by portal
        return True

    def submit_otp_and_book(self, otp_code: str) -> bool:
        logging.info("GVCAdapter: Submitting OTP and final booking payload...")
        url = f"{self.base_url}/appointments/add"
        
        payload = {
            "vac": self.visa_center_cache,
            "type": os.getenv('APPOINTMENT_TYPE', '26'),
            "bookingfor": os.getenv('BOOKING_FOR', '0'),
            "otp": otp_code,
            "g-recaptcha-response": getattr(self, 'booking_captcha_token', '')
        }
        
        if self.applicant_data_cache:
            gvc_payload = {
                "email": self.applicant_data_cache.get('email', ''),
                "phonenumberprefix[id]": self.applicant_data_cache.get('phone_prefix_id', '1'),
                "phonenumber": self.applicant_data_cache.get('phone_number', ''),
                "applicants[][surname]": self.applicant_data_cache.get('surname', ''),
                "applicants[][firstname]": self.applicant_data_cache.get('firstname', ''),
                "applicants[][dateofbirth]": self.applicant_data_cache.get('dateofbirth', ''),
                "applicants[][passportnumber]": self.applicant_data_cache.get('passportnumber', ''),
                "applicants[][traveldocumentvaliduntil]": self.applicant_data_cache.get('passport_expiry', ''),
                "applicants[][gender[id]]": self.applicant_data_cache.get('gender_id', '1'),
                "applicants[][nationality[id]]]": self.applicant_data_cache.get('nationality_id', '1')
            }
            payload.update(gvc_payload)
            if "slot_id" in self.applicant_data_cache:
                payload["periodslot"] = self.applicant_data_cache["slot_id"]

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
        except:
            pass
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, data=payload, headers=headers, timeout=30)
                if response.status_code == 200:
                    logging.info("GVCAdapter: Booking confirmed!")
                    return True
                elif response.status_code in [403, 502, 503, 504, 522]:
                    logging.warning(f"GVCAdapter: Received {response.status_code} during booking. Retrying...")
                    if response.status_code == 403:
                        self.refresh_waf_cookies()
                    time.sleep(3)
                    continue
                else:
                    logging.error(f"GVCAdapter: Booking failed. Status: {response.status_code}")
                    return False
            except Exception as e:
                logging.error(f"GVCAdapter: Network error during booking: {e}")
                if "28" in str(e) or "timeout" in str(e).lower():
                    self.refresh_waf_cookies()
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return False
        return False

    def close(self):
        self.session.cookies.clear()
        if os.path.exists(self.cookie_file):
            try:
                os.remove(self.cookie_file)
            except Exception:
                pass
        logging.info("GVCAdapter: Session closed.")
