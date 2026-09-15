import logging
import time
import os
import json
from typing import Optional
from core.portal_adapter import BasePortalAdapter
from core.browser_persona import BrowserPersona, BrowserPersonaManager
from captcha_service import CaptchaService

class WAFBlockedException(Exception):
    pass

class LoginFailedException(Exception):
    pass

class AlreadyBookedException(Exception):
    pass


class GVCAdapter(BasePortalAdapter):
    def __init__(self, captcha_service: CaptchaService, headless: bool = True, proxy_string: str = None, persona: Optional[BrowserPersona] = None):
        super().__init__(headless)
        self.proxy_string = proxy_string
        self.persona = persona or BrowserPersonaManager.get_random_persona()
        self.logged_in_user = None
        
        try:
            from curl_cffi import requests as c_requests
            self.session = c_requests.Session(impersonate=self.persona.tls_target)
            logging.info(f"GVCAdapter: Initialized polymorphic curl_cffi session with persona '{self.persona.persona_id}' (TLS: {self.persona.tls_target}).")
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

        target_domain = os.getenv('BOOKING_PORTAL_URL', "https://pk-gr-services.gvcworld.eu")
        disable_proxies = os.getenv("DISABLE_PROXIES", "false").lower() in ["true", "1"]
        is_custom_portal = bool(target_domain and "gvcworld.eu" not in target_domain)
        use_mock = os.getenv("USE_MOCK_CAPTCHA", "false").lower() in ["true", "1"]

        if disable_proxies or is_custom_portal or use_mock or "127.0.0.1" in target_domain or "localhost" in target_domain:
            proxy_string = None
            self.proxy_string = None

        if proxy_string:
            self.session.proxies = {"http": proxy_string, "https": proxy_string}
            
        self.base_url = target_domain
        self.sitekey = os.getenv('TARGET_SITEKEY', '6LcnlCoUAAAAAJLjWXXaByTFyuOLf4K0gGu5r3d2')
        self.captcha_service = captcha_service
        self.applicant_data_cache = {}
        self.visa_center_cache = None
        self.booking_captcha_token = ""
        
        # Apply polymorphic default headers
        self.session.headers.update(self.persona.get_default_headers())
        
        self.cookie_file = "gvc-booker-session.pkl"
        self.load_session()
        
        # Monkey-patch session.request to intercept network logs
        self.network_logs = []
        original_request = self.session.request
        
        def intercepted_request(method, url, *args, **kwargs):
            from datetime import datetime
            import json
            req_time = datetime.utcnow()
            try:
                response = original_request(method, url, *args, **kwargs)
                res_time = datetime.utcnow()
                
                req_body = kwargs.get('json') or kwargs.get('data') or ""
                if isinstance(req_body, dict):
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
                        "body": response.text[:5000]
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
                    "user_agent": self.persona.user_agent,
                    "viewport": {'width': self.persona.viewport_width, 'height': self.persona.viewport_height},
                    "extra_http_headers": {
                        "sec-ch-ua": self.persona.sec_ch_ua,
                        "sec-ch-ua-mobile": self.persona.sec_ch_ua_mobile,
                        "sec-ch-ua-platform": f'"{self.persona.sec_ch_ua_platform}"'
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
            
        logging.info(f"GVCAdapter: Attempting login for {username} with persona '{self.persona.persona_id}'...")
        
        # Staggered pre-flight jitter
        self.persona.apply_jitter(multiplier=0.5)
        
        try:
            preflight_headers = {
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
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
                    try:
                        res_json = response.json()
                        self.logged_in_user = res_json.get("user") or res_json
                        token = res_json.get("token") or res_json.get("accessToken")
                        if token:
                            self.session.headers["Authorization"] = f"Bearer {token}"
                    except Exception:
                        pass
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
                    raise LoginFailedException(f"Login failed with status {response.status_code}")
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
                raise WAFBlockedException(f"Network error or timeout during login: {e}")
        raise WAFBlockedException("Max retries exceeded due to WAF blocks or network errors.")

    def inject_applicant_data(self, applicant_data: dict, visa_center: str) -> bool:
        logging.info("GVCAdapter: Caching applicant data for final injection.")
        self.applicant_data_cache = applicant_data
        self.visa_center_cache = str(visa_center)
        return True

    def pass_pre_otp_captcha(self) -> bool:
        logging.info("GVCAdapter: Solving pre-OTP / final booking captcha...")
        self.booking_captcha_token = self.captcha_service.solve(self.sitekey, f"{self.base_url}/appointments/add", session=self.session)
        return bool(self.booking_captcha_token)

    def request_otp(self) -> bool:
        logging.info("GVCAdapter: Triggering OTP via API...")
        phone = self.applicant_data_cache.get('phone_number') or self.applicant_data_cache.get('phone', '')
        prefix_id = self.applicant_data_cache.get('phone_prefix_id', '197')
        if not phone:
            logging.error("GVCAdapter: Cannot request OTP, no phone number available.")
            return False
            
        # Strip leading zeros
        phone_clean = str(phone).lstrip('0')
        url = f"{self.base_url}/api/v1/onetimepassword/sendOtpBookAppointment/{phone_clean}/{prefix_id}"
        
        # Micro-jitter before OTP request
        self.persona.apply_jitter(multiplier=0.4)
        
        try:
            response = self.session.post(url, timeout=30)
            if response.status_code in [200, 204]:
                logging.info("GVCAdapter: OTP requested successfully.")
                return True
            else:
                logging.error(f"GVCAdapter: Failed to request OTP. Status: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"GVCAdapter: Network error requesting OTP: {e}")
            return False

    def submit_otp_and_book(self, otp_code: str) -> bool:
        logging.info(f"GVCAdapter: Submitting OTP and final booking payload with persona '{self.persona.persona_id}'...")
        
        # Primary HAR-verified endpoint
        api_url = f"{self.base_url}/api/v1/appointments"
        
        # Extract applicant fields
        phone = self.applicant_data_cache.get('phone_number') or self.applicant_data_cache.get('phone', '')
        phone_clean = str(phone).lstrip('0')
        prefix_id = str(self.applicant_data_cache.get('phone_prefix_id', '197'))
        email = self.applicant_data_cache.get('email', '')
        
        # Construct HAR-compliant applicant item
        periodslotid = str(self.applicant_data_cache.get('periodslotid') or self.applicant_data_cache.get('slot_id') or '2528256')
        target_date = self.applicant_data_cache.get('target_date', '12/08/2026')
        target_time = self.applicant_data_cache.get('target_time', '12:00')
        app_type = str(os.getenv('APPOINTMENT_TYPE', self.applicant_data_cache.get('type', '26')))
        vac_id = str(self.visa_center_cache or '137')
        
        applicant_obj = {
            "surname": self.applicant_data_cache.get('surname', 'APPLICANT'),
            "firstname": self.applicant_data_cache.get('firstname', 'NAME'),
            "dateofbirth": self.applicant_data_cache.get('dateofbirth') or self.applicant_data_cache.get('dob', '01/01/1990'),
            "passportnumber": self.applicant_data_cache.get('passportnumber') or self.applicant_data_cache.get('passport', 'AB1234567'),
            "traveldocumentvaliduntil": self.applicant_data_cache.get('passport_expiry') or self.applicant_data_cache.get('passport_exp', '01/01/2030'),
            "gender": {"id": str(self.applicant_data_cache.get('gender_id', '2'))},
            "nationality": {"id": str(self.applicant_data_cache.get('nationality_id', '197'))},
            "periodslotid": periodslotid
        }
        
        user_str = "User{id=931995, username=" + email + ", email=" + email + "}"
        if self.logged_in_user and isinstance(self.logged_in_user, dict):
            user_str = json.dumps(self.logged_in_user)
            
        json_payload = {
            "otpuser": user_str,
            "vac": vac_id,
            "type": app_type,
            "bookingfor": "0",
            "members": "1",
            "email": email,
            "phonenumberprefix": {"id": prefix_id},
            "phonenumber": phone_clean,
            "applicants": [applicant_obj],
            "datefrom": target_date,
            "selectedtime": target_time,
            "appointmentmethod": "1",
            "submitinfo": "on",
            "submissionMsgCheck": "Make sure that you have checked the required checkbox",
            "onetimepassword": str(otp_code),
            "g-recaptcha-response": self.booking_captcha_token or "mock_token"
        }
        
        # Jitter before final booking submission
        self.persona.apply_jitter(multiplier=0.6)
        
        try:
            self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
        except:
            pass
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(api_url, json=json_payload, timeout=30)
                if response.status_code in [200, 201]:
                    logging.info("GVCAdapter: REST Booking confirmed successfully (200 OK)!")
                    try:
                        self.session.post(f"{self.base_url}/appointments/result/null", timeout=5)
                    except:
                        pass
                    return True
                elif response.status_code == 404:
                    # Fallback to legacy form-encoded /appointments/add endpoint if server uses legacy route
                    logging.info("GVCAdapter: REST endpoint 404, attempting legacy form endpoint...")
                    legacy_payload = {
                        "vac": vac_id,
                        "type": app_type,
                        "bookingfor": "0",
                        "otp": otp_code,
                        "g-recaptcha-response": self.booking_captcha_token or "mock_token",
                        "email": email,
                        "phonenumberprefix[id]": prefix_id,
                        "phonenumber": phone_clean,
                        "applicants[][surname]": applicant_obj["surname"],
                        "applicants[][firstname]": applicant_obj["firstname"],
                        "applicants[][dateofbirth]": applicant_obj["dateofbirth"],
                        "applicants[][passportnumber]": applicant_obj["passportnumber"],
                        "applicants[][traveldocumentvaliduntil]": applicant_obj["traveldocumentvaliduntil"],
                        "applicants[][gender[id]]": applicant_obj["gender"]["id"],
                        "applicants[][nationality[id]]]": applicant_obj["nationality"]["id"],
                        "periodslot": periodslotid
                    }
                    leg_res = self.session.post(f"{self.base_url}/appointments/add", data=legacy_payload, headers={'Content-Type': 'application/x-www-form-urlencoded'}, timeout=30)
                    if leg_res.status_code == 200:
                        logging.info("GVCAdapter: Legacy Booking confirmed!")
                        return True
                    else:
                        leg_text_lower = leg_res.text.lower()
                        if any(k in leg_text_lower for k in ["already booked", "already registered", "already exists", "active appointment", "duplicate", "duplicate_applicant", "has already booked", "passport already in use", "passport number already has an appointment"]):
                            logging.warning(f"GVCAdapter: Portal returned duplicate/already-booked error: {leg_res.text[:200]}")
                            raise AlreadyBookedException(f"Portal rejected: Active appointment already exists for this passport ({leg_res.text[:150]})")
                        logging.error(f"GVCAdapter: Legacy booking failed. Status: {leg_res.status_code}")
                        return False
                elif response.status_code in [403, 502, 503, 504, 522]:
                    logging.warning(f"GVCAdapter: Received {response.status_code} during booking. Retrying...")
                    if response.status_code == 403:
                        self.refresh_waf_cookies()
                        if attempt == max_retries - 1:
                            raise WAFBlockedException(f"Portal WAF Challenge (HTTP 403): {response.text[:120]}")
                    time.sleep(3)
                    continue
                else:
                    resp_text_lower = response.text.lower()
                    if any(k in resp_text_lower for k in ["already booked", "already registered", "already exists", "active appointment", "duplicate", "duplicate_applicant", "has already booked", "passport already in use", "passport number already has an appointment"]):
                        logging.warning(f"GVCAdapter: Portal returned duplicate/already-booked error: {response.text[:200]}")
                        raise AlreadyBookedException(f"Portal rejected: Active appointment already exists for this passport ({response.text[:150]})")
                    logging.error(f"GVCAdapter: Booking failed. Status: {response.status_code}, Body: {response.text[:200]}")
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
