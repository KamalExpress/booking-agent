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

os.makedirs('logs', exist_ok=True)
log_filename = f"logs/runlog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure logging to write to both the file and the console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

class OperatorAgent:
    def __init__(self, captcha_service: CaptchaService):
        self.session = requests.Session()
        # Set some common headers to mimic a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        })
        
        self.username = os.getenv('GVC_USERNAME')
        self.password = os.getenv('GVC_PASSWORD')
        self.base_url = os.getenv('BASE_URL', 'https://pk-gr-services.gvcworld.eu')
        self.sitekey = os.getenv('TARGET_SITEKEY', '6LcnlCoUAAAAAJLjWXXaByTFyuOLf4K0gGu5r3d2')
        self.captcha_service = captcha_service
        
        internal_portal = os.getenv('INTERNAL_PORTAL_URL', 'http://localhost:5001')
        otp_endpoint = f"{internal_portal}/get-otp"
        otp_key = os.getenv('OTP_API_KEY', 'dummy_key')
        self.otp_service = OTPService(api_endpoint=otp_endpoint, api_key=otp_key)

    def login(self):
        logging.info(f"Attempting login for {self.username}...")
        
        captcha_token = self.captcha_service.solve(self.sitekey, f"{self.base_url}/login", session=self.session)
        
        url = f"{self.base_url}/api/v1/auth/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "g-recaptcha-response": captcha_token
        }
        
        logging.debug(f"Login payload: {payload}")
        response = self.session.post(url, json=payload)
        logging.debug(f"Login response status: {response.status_code}, text: {response.text}")
        
        if response.status_code == 200:
            logging.info("Login successful!")
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
        logging.info(f"Searching for slots from {date_from}...")
        
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
        
        logging.debug(f"Search slots payload: {payload}")
        response = self.session.put(url, json=payload)
        logging.debug(f"Search slots response status: {response.status_code}, text: {response.text}")
        
        if response.status_code == 200:
            slots = response.json()
            logging.info(f"Slots retrieved successfully: {slots}")
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
    logging.info("Using Mock Captcha Service for local demo.")
    captcha_svc = MockCaptchaService()
        
    agent = OperatorAgent(captcha_service=captcha_svc)
    
    if not agent.username or not agent.password:
        logging.error("Credentials not found in environment. Please setup .env file.")
        return
        
    max_slots = int(os.getenv('MAX_SLOTS_TO_BOOK', '5'))
    
    while True:
        # Check global counter across parallel processes using a lock file
        lock_file = "lock.txt"
        count_file = "booked.txt"
        
        while True:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
            except FileExistsError:
                time.sleep(0.1)
                
        try:
            count = 0
            if os.path.exists(count_file):
                with open(count_file, "r") as f:
                    c = f.read().strip()
                    count = int(c) if c else 0
                    
            if count >= max_slots:
                print("\n*** max slot limit reached ***\n")
                logging.info("max slot limit reached")
                os.close(fd)
                os.remove(lock_file)
                break
                
            with open(count_file, "w") as f:
                f.write(str(count + 1))
        finally:
            try:
                os.close(fd)
                os.remove(lock_file)
            except:
                pass

        if agent.login():
            date_from = os.getenv('APPOINTMENT_DATE_FROM', '09/07/2026')
            app_type = os.getenv('APPOINTMENT_TYPE', '26')
            vac_id = os.getenv('APPOINTMENT_VAC_ID', '138')
            
            slots_response = agent.search_slots(date_from, app_type, vac_id)
            
            if slots_response and slots_response.get("code") == "SUCCESS":
                slots = slots_response.get("returnobject", {}).get("slots", [])
                
                # Gather all available slots
                available_slots = [slot for slot in slots if slot.get('isavailable') and slot.get('isselectable')]
                
                if not available_slots:
                    logging.error("No available slots found for booking.")
                    # Decrement counter since we failed
                    while True:
                        try:
                            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                            break
                        except FileExistsError:
                            time.sleep(0.1)
                    try:
                        if os.path.exists(count_file):
                            with open(count_file, "r") as f:
                                c = int(f.read().strip())
                                with open(count_file, "w") as fw:
                                    fw.write(str(max(0, c - 1)))
                    finally:
                        try:
                            os.close(fd)
                            os.remove(lock_file)
                        except:
                            pass
                    break
                    
                # Pick a random slot to heavily reduce collision probability among parallel bots
                import random
                chosen = random.choice(available_slots)
                selected_slot = {"id": chosen['id'], "time": chosen['starttime'], "date": date_from}
                    
                logging.info(f"Selected available slot: {selected_slot}")
                
                internal_portal = os.getenv('INTERNAL_PORTAL_URL', 'http://localhost:5001')
                applicants_url = f"{internal_portal}/get-applicants"
                try:
                    logging.info(f"Fetching applicant data from {applicants_url}...")
                    apps_response = requests.get(applicants_url).json()
                    if apps_response and len(apps_response) > 0:
                        internal_app = apps_response[0] 
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
                            success = agent.book_appointment(selected_slot, otp, applicant_data)
                            if success:
                                try:
                                    requests.post(f"{internal_portal}/update-status", json={
                                        "id": internal_app.get("id"),
                                        "slot": selected_slot
                                    })
                                    logging.info(f"Reported successful booking of slot {selected_slot['id']} to internal portal for applicant {internal_app.get('firstname')}")
                                except Exception as e:
                                    logging.error(f"Failed to update internal portal status: {e}")
                                return  # Successfully booked! Terminate the script.
                            if not success:
                                # Decrement on failure
                                pass # Simplified for demo
                    else:
                        logging.error("No applicants found in internal DB.")
                except Exception as e:
                    logging.error(f"Failed to fetch applicants from {applicants_url}: {e}")

if __name__ == "__main__":
    main()
