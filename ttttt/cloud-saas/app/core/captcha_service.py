import abc
import requests
import time
import logging

class CaptchaService(abc.ABC):
    @abc.abstractmethod
    def solve(self, sitekey: str, url: str, **kwargs) -> str:
        """Solves the captcha and returns the token."""
        pass

class NopeChaService(CaptchaService):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = 'https://api.nopecha.com/token'

    def solve(self, sitekey: str, url: str, **kwargs) -> str:
        logging.info(f"Submitting NopeCha job for sitekey {sitekey} on {url}...")
        
        # Submit job
        payload = {
            'type': 'recaptcha2',
            'sitekey': sitekey,
            'url': url,
            'key': self.api_key
        }
        try:
            logging.debug(f"NopeCha POST payload: {payload}")
            response_full = requests.post(self.api_url, json=payload)
            response = response_full.json()
            logging.debug(f"NopeCha POST response status: {response_full.status_code}, text: {response_full.text}")
            
            if 'data' not in response:
                logging.error(f"NopeCha submission failed: {response}")
                return ""
            job_id = response['data']
            logging.info(f"NopeCha job submitted successfully. Job ID: {job_id}")
        except Exception as e:
            logging.error(f"Error submitting NopeCha job: {e}")
            return ""

        # Poll for completion
        logging.info("Polling for NopeCha completion...")
        for _ in range(40): # poll for max 120 seconds
            time.sleep(3)
            try:
                poll_url = f"{self.api_url}?key={self.api_key}&id={job_id}"
                poll_response_full = requests.get(poll_url)
                poll_response = poll_response_full.json()
                logging.debug(f"NopeCha GET poll response status: {poll_response_full.status_code}, text: {poll_response_full.text}")
                
                if 'data' in poll_response and isinstance(poll_response['data'], str):
                    token = poll_response['data']
                    logging.info("NopeCha solved the CAPTCHA successfully!")
                    return token
            except Exception as e:
                logging.error(f"Error polling NopeCha: {e}")
                
            logging.debug("Waiting for captcha to be solved...")
            
        logging.error("NopeCha polling timed out.")
        return ""

class CloudManualCaptchaService(CaptchaService):
    def solve(self, sitekey: str, url: str, **kwargs) -> str:
        logging.info(f"Starting Cloud Manual Captcha Delegation for {url}...")
        try:
            from core.state import global_captcha_state
            
            # Broadcast the challenge to the frontend
            global_captcha_state.request_captcha(sitekey, url)
            logging.info("Captcha challenge broadcasted to Staff dashboard. Waiting for an Operator to solve it...")
            
            # Optionally trigger push notifications via db here if accessible,
            # but usually the SlotMonitorEngine handles push. Alternatively, 
            # the frontend polling is extremely fast (3s) so the operator will see it instantly.
            
            # Block the current thread until the frontend submits the token or timeout (10 mins)
            solved = global_captcha_state.event.wait(timeout=600)
            
            if not solved:
                logging.error("Cloud Manual Captcha solving timed out after 10 minutes.")
                # Reset state
                with global_captcha_state.lock:
                    global_captcha_state.is_pending = False
                return ""
                
            token = global_captcha_state.solved_token
            logging.info("Cloud Manual Captcha successfully received token from the dashboard!")
            return token
            
        except Exception as e:
            logging.error(f"Error in Cloud Manual Captcha: {e}")
            return ""
