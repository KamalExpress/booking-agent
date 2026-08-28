import logging
import time
import os
import json
from typing import Any, Optional
from core.adapters.base_adapter import BasePortalAdapter
from core.adapters.adapter_factory import AdapterFactory
from captcha_service import CaptchaService

class WAFBlockedException(Exception):
    pass

class LoginFailedException(Exception):
    pass

@AdapterFactory.register("GVC")
class GVCAdapter(BasePortalAdapter):
    def __init__(self, captcha_service: CaptchaService = None, headless: bool = True, proxy_string: str = None):
        super().__init__(captcha_service, headless, proxy_string)
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
            
        target_domain = os.getenv('BOOKING_PORTAL_URL', "https://pk-gr-services.gvcworld.eu")
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Origin": target_domain,
            "Referer": f"{target_domain}/?lang=en_US",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        })
        
        self.base_url = target_domain
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
        self.visa_center_cache = visa_center
        return True

    def search_slots(self, session: Any, date_from: str, app_type: str, vac_id: str) -> Optional[list]:
        """
        Search for available slots. (Imported from old slot_monitor.py logic)
        """
        url = f"{self.base_url}/api/v1/periodslot/slots"
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
        
        try:
            # Using the passed in session, or self.session if None
            s = session if session else self.session
            response = s.put(url, json=payload, timeout=20)
            if response.status_code == 200:
                slots_data = response.json()
                if slots_data and slots_data.get("code") == "SUCCESS":
                    ret_obj = slots_data.get("returnobject")
                    slots = ret_obj.get("slots", []) if isinstance(ret_obj, dict) else (ret_obj if isinstance(ret_obj, list) else [])
                    return slots
                return []
            elif response.status_code in [401, 403]:
                logging.error(f"GVCAdapter: search_slots hit WAF/Auth error ({response.status_code})")
                return None
                logging.warning(f"GVCAdapter: Unexpected status code {response.status_code} in search_slots")
                return None
        except Exception as e:
            logging.error(f"Exception during search_slots: {e}")
            return None

    def inject_applicant_data(self, applicant_data: dict, visa_center_id: str):
        import re
        logging.info(f"GVCAdapter: Navigating to booking page and binding applicant {applicant_data.get('email')}...")
        self.applicant_data_cache = applicant_data.copy()
        self.visa_center_cache = str(visa_center_id)
        
        # 1. Pre-flight navigation to /appointments/add to initialize booking session and capture hidden otpuser token
        try:
            url = f"{self.base_url}/appointments/add"
            response = self.session.post(url, timeout=30)
            if response.status_code == 200:
                match = re.search(r'<input[^>]*id=["\']otpuser["\'][^>]*value=["\']([^"\']+)["\']', response.text)
                if not match:
                    match = re.search(r'<input[^>]*name=["\']otpuser["\'][^>]*value=["\']([^"\']+)["\']', response.text)
                if match:
                    self.otpuser_cache = match.group(1)
                    logging.info(f"GVCAdapter: Successfully captured hidden otpuser session token ({self.otpuser_cache[:30]}...)")
                else:
                    self.otpuser_cache = None
                    logging.warning("GVCAdapter: Could not find hidden #otpuser input in /appointments/add HTML response.")
        except Exception as e:
            logging.error(f"GVCAdapter: Error during pre-flight navigation to /appointments/add: {e}")
            self.otpuser_cache = None

    def pass_pre_otp_captcha(self) -> bool:
        logging.info("GVCAdapter: Solving pre-OTP / final booking captcha...")
        self.booking_captcha_token = self.captcha_service.solve(self.sitekey, f"{self.base_url}/appointments/add", session=self.session)
        return bool(self.booking_captcha_token)

    def request_otp(self) -> bool:
        logging.info("GVCAdapter: Triggering SMS OTP via portal API...")
        phone = self.applicant_data_cache.get('phone_number', '')
        prefix_id = str(self.applicant_data_cache.get('phone_prefix_id', '197'))
        if not phone:
            logging.error("GVCAdapter: Cannot request OTP, no phone number available.")
            return False
            
        # Clean leading zeros for GVC format (e.g. 03345112969 -> 3345112969)
        phone_clean = phone.lstrip("0")
        url = f"{self.base_url}/api/v1/onetimepassword/sendOtpBookAppointment/{phone_clean}/{prefix_id}"
        
        headers = {
            "Accept": "*/*",
            "Referer": f"{self.base_url}/appointments/add",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        try:
            response = self.session.post(url, headers=headers, timeout=30)
            logging.info(f"GVCAdapter: OTP request response status {response.status_code}: {response.text}")
            
            # Save raw network trace
            self._log_raw_har_entry("POST", url, headers, "", response.status_code, response.text)
            
            if response.status_code in [200, 204]:
                try:
                    resp_json = response.json()
                    if resp_json.get("code") == "SUCCESS" or "sent by SMS" in resp_json.get("message", ""):
                        logging.info("GVCAdapter: Portal confirmed OTP sent by SMS.")
                        return True
                except Exception:
                    pass
                return True
            else:
                logging.error(f"GVCAdapter: Portal rejected OTP request. Status: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"GVCAdapter: Network error requesting OTP: {e}")
            return False

    def submit_otp_and_book(self, otp_code: str, task_id: int = None) -> tuple[bool, dict]:
        import re
        import json
        from datetime import datetime
        
        logging.info("GVCAdapter: Submitting OTP and final booking payload...")
        url = f"{self.base_url}/api/v1/appointments"
        
        phone_raw = self.applicant_data_cache.get('phone_number', '')
        phone_clean = phone_raw.lstrip("0")
        prefix_id = str(self.applicant_data_cache.get('phone_prefix_id', '197'))
        slot_id = str(self.applicant_data_cache.get('slot_id', ''))
        target_date = self.applicant_data_cache.get('target_date', '')
        target_time = self.applicant_data_cache.get('target_time', '09:30')
        
        # Build exact JSON payload matching GVC HAR recording
        payload = {
            "otpuser": getattr(self, "otpuser_cache", "") or f"User{{id=9999, username={self.applicant_data_cache.get('email')}}}",
            "vac": str(self.visa_center_cache),
            "type": str(os.getenv('APPOINTMENT_TYPE', '26')),
            "bookingfor": "0",
            "members": "1",
            "email": self.applicant_data_cache.get('email', ''),
            "phonenumberprefix": {"id": prefix_id},
            "phonenumber": phone_clean,
            "applicants": [
                {
                    "surname": self.applicant_data_cache.get('surname', '').upper(),
                    "firstname": self.applicant_data_cache.get('firstname', '').upper(),
                    "dateofbirth": self.applicant_data_cache.get('dateofbirth', ''),
                    "passportnumber": self.applicant_data_cache.get('passportnumber', '').upper(),
                    "traveldocumentvaliduntil": self.applicant_data_cache.get('passport_expiry', ''),
                    "gender": {"id": str(self.applicant_data_cache.get('gender_id', '1'))},
                    "nationality": {"id": str(self.applicant_data_cache.get('nationality_id', '197'))},
                    "periodslotid": slot_id
                }
            ],
            "datefrom": target_date,
            "selectedtime": target_time,
            "appointmentmethod": "1",
            "submitinfo": "on",
            "submissionMsgCheck": "Make sure that you have checked the required checkbox",
            "onetimepassword": str(otp_code),
            "g-recaptcha-response": getattr(self, 'booking_captcha_token', '')
        }
        
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json; charset=UTF-8",
            "Referer": f"{self.base_url}/appointments/add",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        try:
            self.session.get(f"{self.base_url}/favicon.ico", timeout=3)
        except Exception:
            pass
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, json=payload, headers=headers, timeout=30)
                logging.info(f"GVCAdapter: Booking submission response status {response.status_code}: {response.text}")
                
                # Save raw HAR entry
                self._log_raw_har_entry("POST", url, headers, json.dumps(payload), response.status_code, response.text)
                
                if response.status_code == 200:
                    try:
                        resp_json = response.json()
                        code = resp_json.get("code")
                        msg = resp_json.get("message", "")
                        
                        if code == "INVALID" or "Mismatch OTP" in msg or "expired" in msg.lower():
                            logging.error(f"GVCAdapter: OTP Error from portal: {msg}")
                            return False, {"reason": f"OTP Error: {msg}", "code": "INVALID_OTP", "portal_message": msg}
                        elif "slot" in msg.lower() and ("unavailable" in msg.lower() or "no longer" in msg.lower()):
                            logging.error(f"GVCAdapter: Slot no longer available: {msg}")
                            return False, {"reason": f"Slot Unavailable: {msg}", "code": "SLOT_TAKEN", "portal_message": msg}
                        elif code not in ["SUCCESS", None] and not resp_json.get("returnobject"):
                            logging.error(f"GVCAdapter: Portal returned non-success code ({code}): {msg}")
                            return False, {"reason": f"Portal Error ({code}): {msg}", "code": code, "portal_message": msg}
                    except Exception:
                        pass
                        
                    logging.info("GVCAdapter: Booking confirmed by portal!")
                    
                    # 1. Scrape Reference Number from response text / JSON
                    ref_number = "CONFIRMED-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    try:
                        resp_json = response.json()
                        if isinstance(resp_json, dict):
                            ret_obj = resp_json.get("returnobject") or {}
                            ref_number = ret_obj.get("reference") or ret_obj.get("appointmentId") or ref_number
                    except Exception:
                        ref_match = re.search(r'(?:Reference|Appointment\s*(?:ID|Code|No)|Ref)[:\s#]+([A-Z0-9\-]+)', response.text, re.IGNORECASE)
                        if ref_match:
                            ref_number = ref_match.group(1)
                            
                    # 2. Capture and persist confirmation artifact
                    confirmations_dir = os.path.join(os.getcwd(), "data", "confirmations")
                    os.makedirs(confirmations_dir, exist_ok=True)
                    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    task_tag = f"task_{task_id}" if task_id else "booking"
                    receipt_filename = f"{task_tag}_{ref_number}_{timestamp_str}.html"
                    receipt_path = os.path.join(confirmations_dir, receipt_filename)
                    
                    with open(receipt_path, "w", encoding="utf-8") as f:
                        f.write(f"<!-- Confirmation Receipt for Task {task_id} -->\n")
                        f.write(f"<!-- Reference: {ref_number} | Time: {datetime.utcnow().isoformat()} -->\n")
                        f.write(response.text)
                        
                    result_data = {
                        "reference_number": ref_number,
                        "confirmation": response.text[:1000], # preview snippet
                        "screenshot_path": receipt_path,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    return True, result_data
                    
                elif response.status_code in [403, 502, 503, 504, 522]:
                    logging.warning(f"GVCAdapter: Received {response.status_code} during booking. Retrying... ({attempt+1}/{max_retries})")
                    if response.status_code == 403:
                        self.refresh_waf_cookies()
                    time.sleep(3)
                    continue
                else:
                    logging.error(f"GVCAdapter: Booking failed. Status: {response.status_code} - {response.text}")
                    return False, {"reason": f"Status {response.status_code}: {response.text[:200]}"}
            except Exception as e:
                logging.error(f"GVCAdapter: Network error during booking: {e}")
                if "28" in str(e) or "timeout" in str(e).lower():
                    self.refresh_waf_cookies()
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return False, {"reason": f"Network error: {str(e)}"}
        return False, {"reason": "Max retries exceeded during final submission"}

    def _log_raw_har_entry(self, method: str, url: str, headers: dict, body: str, status: int, resp_text: str):
        """Persists every raw HTTP transaction into data/har_logs/ for real-time traffic capture."""
        try:
            import json
            from datetime import datetime
            har_dir = os.path.join(os.getcwd(), "data", "har_logs")
            os.makedirs(har_dir, exist_ok=True)
            today_str = datetime.utcnow().strftime("%Y%m%d")
            har_file = os.path.join(har_dir, f"booking_traffic_{today_str}.jsonl")
            
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "request": {
                    "method": method,
                    "url": url,
                    "headers": {k: str(v) for k, v in headers.items()},
                    "body": body
                },
                "response": {
                    "status": status,
                    "body": resp_text[:4000]
                }
            }
            with open(har_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logging.warning(f"Failed to log raw HAR entry: {e}")

    def close(self):
        self.session.cookies.clear()
        if os.path.exists(self.cookie_file):
            try:
                os.remove(self.cookie_file)
            except Exception:
                pass
        logging.info("GVCAdapter: Session closed.")
