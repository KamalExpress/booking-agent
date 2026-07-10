# Automated OTP Integration & HAR Analysis Plan

Based on your comments, here is the updated plan to fully automate the OTP step and the results of our further HAR analysis.

## 1. HAR File Analysis

I re-examined the `login-data-entry-search-slots.txt` HAR file to find any API calls related to requesting the OTP or the final booking step.

> [!WARNING]
> **HAR Trace Ends Early:** The HAR file you provided only captures network traffic up to the slot search (`/api/v1/periodslot/slots`). It does **not** contain the network requests that occur when you click "Send OTP" or "Book Appointment".
>
> Because of this, we don't currently know the exact API endpoint to *trigger* the SMS OTP to be sent to the phone. Does the portal automatically send the OTP when you click a certain slot, or is there a specific "Send OTP" button the user clicks? If there is a button, we will need to capture that specific network request later.

## 2. Automated OTP Polling Integration

To automate the OTP retrieval from your mobile app's database API, we will create a dedicated `OTPService` class in a new `otp_service.py` file. This service will periodically poll your custom API endpoint until the OTP is found.

### Proposed Architecture

**1. Create `otp_service.py`:**
```python
import time
import requests
import logging

class OTPService:
    def __init__(self, api_endpoint: str, api_key: str = None):
        self.api_endpoint = api_endpoint
        self.api_key = api_key

    def fetch_otp(self, phone_number: str) -> str:
        logging.info(f"Polling custom API for OTP for {phone_number}...")
        # Poll every 5 seconds for up to 2 minutes
        for _ in range(24):
            time.sleep(5)
            try:
                # Example request structure
                response = requests.get(f"{self.api_endpoint}?phone={phone_number}")
                data = response.json()
                if 'otp' in data and data['otp']:
                    logging.info("OTP retrieved successfully!")
                    return data['otp']
            except Exception as e:
                logging.error(f"Error polling OTP API: {e}")
            logging.debug("Waiting for OTP...")
        
        logging.error("OTP polling timed out.")
        return None
```

**2. Update `.env.example`:**
Add configurations for the new OTP API:
`OTP_API_ENDPOINT=https://your-custom-db-api.com/get-otp`
`OTP_API_KEY=your_optional_secret`

**3. Inject into `OperatorAgent`:**
Update `operator.py` to instantiate `OTPService` and pass it into the `OperatorAgent` just like we did with the `CaptchaService`. Replace the `input()` prompt in `request_otp()` with a call to `self.otp_service.fetch_otp(self.phone_number)`.

## User Review Required

> [!IMPORTANT]
> **OTP Trigger Request:** Since the HAR file is missing the "Send OTP" button click, the script currently does not know how to tell the portal to send the SMS. If the portal requires an API call to trigger the SMS, you will need to capture that specific request for me. If the SMS is sent automatically, then the polling service outlined above is all we need.
>
> Do you approve this architecture for the `OTPService` polling logic?
