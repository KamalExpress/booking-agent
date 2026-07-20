import logging
import time
import os
from core.portal_adapter import BasePortalAdapter
from captcha_service import CaptchaService

class GVCAdapter(BasePortalAdapter):
    def __init__(self, captcha_service: CaptchaService, headless: bool = True, proxy_string: str = None):
        super().__init__(headless)
        try:
            from curl_cffi import requests as c_requests
            self.session = c_requests.Session(impersonate="chrome120")
            logging.info("GVCAdapter: Using curl_cffi Chrome impersonation.")
        except ImportError:
            import requests
            self.session = requests.Session()
            logging.warning("GVCAdapter: curl_cffi not found. Using standard requests.")

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

    def login(self, username: str, password: str) -> bool:
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
            response = self.session.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                logging.info("GVCAdapter: Login successful!")
                return True
            else:
                logging.error(f"GVCAdapter: Login failed. Status: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"GVCAdapter: Network error during login: {e}")
            return False

    def inject_applicant_data(self, applicant_data: dict, visa_center: str) -> bool:
        logging.info("GVCAdapter: Caching applicant data for final injection.")
        self.applicant_data_cache = applicant_data
        self.visa_center_cache = visa_center
        return True

    def pass_pre_otp_captcha(self) -> bool:
        # Pre-OTP captcha might be needed if they have one before SMS
        logging.info("GVCAdapter: Solving pre-OTP / final booking captcha...")
        self.booking_captcha_token = self.captcha_service.solve(self.sitekey, f"{self.base_url}/appointments/add", session=self.session)
        return bool(self.booking_captcha_token)

    def request_otp(self) -> bool:
        logging.info("GVCAdapter: Triggering OTP via API...")
        # Placeholder for actual OTP trigger request.
        # url = f"{self.base_url}/api/v1/otp/send"
        # self.session.post(url, json={"phone": self.applicant_data_cache.get("phone_number")})
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
            # Map standard applicant dict to GVC specific form payload
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
            
            # Note: Slot ID (periodslot) must also be passed if it's a specific slot booking. 
            # In waitlist auto-dispatch, the worker might need to grab an available slot here first.
            # If the headless_booker assigns the slot, it would pass it in the applicant_data.
            if "slot_id" in self.applicant_data_cache:
                payload["periodslot"] = self.applicant_data_cache["slot_id"]

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            response = self.session.post(url, data=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                logging.info("GVCAdapter: Booking confirmed!")
                return True
            else:
                logging.error(f"GVCAdapter: Booking failed. Status: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"GVCAdapter: Network error during booking: {e}")
            return False

    def close(self):
        self.session.cookies.clear()
        logging.info("GVCAdapter: Session closed.")
