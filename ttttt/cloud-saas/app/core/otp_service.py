import time
import requests
import logging

class OTPService:
    def __init__(self, api_endpoint: str, api_key: str = None):
        self.api_endpoint = api_endpoint
        self.api_key = api_key

    def fetch_otp(self, phone_number: str) -> str:
        """
        Polls the custom DB API for the SMS OTP sent to the given phone number.
        """
        if not self.api_endpoint:
            logging.error("OTP_API_ENDPOINT is not configured.")
            return None

        logging.info(f"Polling custom API for OTP for phone {phone_number}...")
        
        # Poll every 5 seconds for up to 2 minutes
        for _ in range(24):
            time.sleep(5)
            try:
                # Assuming the API takes the phone number as a query parameter.
                # If an API key is required, we could send it in headers or params.
                headers = {}
                if self.api_key:
                    headers['Authorization'] = f"Bearer {self.api_key}"
                    
                response = requests.get(f"{self.api_endpoint}?phone={phone_number}", headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    # Expecting something like {"otp": "123456"}
                    if 'otp' in data and data['otp']:
                        logging.info(f"OTP retrieved successfully: {data['otp']}")
                        return data['otp']
                else:
                    logging.debug(f"OTP API returned status {response.status_code}")
                    
            except Exception as e:
                logging.error(f"Error polling OTP API: {e}")
                
            logging.debug("Waiting for OTP...")
        
        logging.error("OTP polling timed out.")
        return None
