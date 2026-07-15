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
    def __init__(self, captcha_service: CaptchaService, username: str = None, password: str = None):
        self.session = requests.Session()
        
        # Add retry logic to handle RemoteDisconnected (server drops keep-alive)
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
        
        # Standardize headers to match Playwright context and bypass anti-bot
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Origin": "https://pk-gr-services.gvcworld.eu",
            "Referer": "https://pk-gr-services.gvcworld.eu/"
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

    def load_session(self):
        import pickle
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, 'rb') as f:
                    self.session.cookies.update(pickle.load(f))
                logging.info("Loaded previous session cookies from file.")
            except Exception as e:
                logging.warning(f"Could not load previous session: {e}")

    def save_session(self):
        import pickle
        try:
            with open(self.cookie_file, 'wb') as f:
                pickle.dump(self.session.cookies, f)
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

    def login(self):
        logging.info(f"Attempting login for {self.username}...")
        
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
        try:
            response = self.session.post(url, json=payload)
            logging.debug(f"Login response status: {response.status_code}, text: {response.text}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during login request: {e}")
            return False
        
        if response.status_code == 200:
            logging.info("Login successful!")
            self.save_session()
            # Save auth token if returned in JSON (sometimes it's a cookie, sometimes an Authorization header)
            # data = response.json()
            # if 'token' in data:
            #     self.session.headers.update({'Authorization': f"Bearer {data['token']}"})
            return True
        else:
            logging.error(f"Login failed. Status Code: {response.status_code}")
            logging.error(f"Response: {response.text}")
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
        response = self.session.put(url, json=payload)
        logging.debug(f"Search slots response status: {response.status_code}, text: {response.text}")
        
        if response.status_code == 200:
            slots = response.json()
            logging.info(f"Slots retrieved successfully from {url}: {slots}")
            return slots
        else:
            logging.error(f"Failed to search slots. Status Code: {response.status_code}")
            logging.error(f"Response: {response.text}")
            return None

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
        response = self.session.post(url, data=payload, headers=headers)
        
        logging.debug(f"Book appointment response status: {response.status_code}, text: {response.text}")
        
        if response.status_code == 200:
            logging.info("Booking confirmed!")
            return True
        else:
            logging.error(f"Booking failed. Status Code: {response.status_code}")
            logging.error(f"Response: {response.text}")
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
