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

class CapSolverService(CaptchaService):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.create_task_url = "https://api.capsolver.com/createTask"
        self.get_result_url = "https://api.capsolver.com/getTaskResult"

    def solve(self, sitekey: str, url: str, **kwargs) -> str:
        max_attempts = 2
        
        for attempt in range(1, max_attempts + 1):
            logging.info(f"[Attempt {attempt}/{max_attempts}] Submitting CapSolver job for sitekey {sitekey} on {url}...")
            
            payload = {
                "clientKey": self.api_key,
                "task": {
                    "type": "ReCaptchaV2TaskProxyless",
                    "websiteURL": url,
                    "websiteKey": sitekey
                }
            }
            
            try:
                res = requests.post(self.create_task_url, json=payload).json()
                if res.get("errorId") != 0:
                    logging.error(f"CapSolver creation failed: {res}")
                    continue
                
                task_id = res.get("taskId")
                logging.info(f"CapSolver job submitted successfully. Task ID: {task_id}")
                
                # Poll for completion
                logging.info("Polling for CapSolver completion... (Max 150 seconds)")
                for _ in range(50): # poll for max 150 seconds (50 * 3s)
                    time.sleep(3)
                    poll_payload = {
                        "clientKey": self.api_key,
                        "taskId": task_id
                    }
                    poll_res = requests.post(self.get_result_url, json=poll_payload).json()
                    status = poll_res.get("status")
                    
                    if status == "ready":
                        token = poll_res.get("solution", {}).get("gRecaptchaResponse", "")
                        logging.info("CapSolver solved the CAPTCHA successfully!")
                        return token
                    elif status == "failed":
                        logging.error(f"CapSolver task failed: {poll_res.get('errorDescription')}")
                        break # break inner polling loop, retry outer loop
                    
                    logging.debug(f"Waiting for CapSolver... current status: {status}")
                    
                logging.warning(f"CapSolver attempt {attempt} timed out or failed.")
            except Exception as e:
                logging.error(f"Error during CapSolver job: {e}")
                
        logging.error("CapSolver failed after maximum attempts.")
        return ""

class ManualCaptchaService(CaptchaService):
    def solve(self, sitekey: str, url: str, **kwargs) -> str:
        session = kwargs.get('session')
        logging.info(f"Starting Manual Captcha Solver for {url}...")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logging.error("Playwright is not installed. Run 'pip install playwright' and 'playwright install chromium'")
            return ""

        with sync_playwright() as p:
            # Launch real Chrome browser so human can solve
            browser = p.chromium.launch(headless=False, channel="chrome")
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            logging.info("Navigating to the login page...")
            try:
                page.goto(url)
            except Exception as e:
                logging.error(f"Playwright failed to navigate to login page: {e}")
                browser.close()
                return None
            
            # Autofill credentials so the human doesn't have to
            import os
            username = os.getenv('GVC_USERNAME', '')
            password = os.getenv('GVC_PASSWORD', '')
            if username and password:
                try:
                    # Attempt standard login form selectors
                    page.fill('input[name="username"], input[type="email"], input[id*="user"]', username, timeout=2000)
                    page.fill('input[name="password"], input[type="password"], input[id*="pass"]', password, timeout=2000)
                    logging.info("Autofilled username and password in browser.")
                except Exception:
                    logging.info("Could not autofill credentials, login fields not found on this page.")
            
            logging.info("Waiting for you to manually solve the Captcha... You have 300 seconds (5 minutes).")
            print("\n*** PLEASE SOLVE THE CAPTCHA IN THE OPENED BROWSER WINDOW ***\n")
            
            # Play a loud beep to alert the operator
            try:
                import winsound
                # Play 3 short beeps
                for _ in range(3):
                    winsound.Beep(1000, 500)
                    time.sleep(0.1)
            except Exception as e:
                logging.error(f"Could not play alarm sound: {e}")
            
            # Poll the hidden textarea for the token
            # g-recaptcha-response is the standard hidden textarea populated after solving
            token = ""
            for _ in range(150): # 150 * 2 = 300 seconds timeout
                try:
                    # Evaluate javascript to get the value of the textarea
                    val = page.evaluate("document.getElementById('g-recaptcha-response') ? document.getElementById('g-recaptcha-response').value : ''")
                    if val and len(val) > 10:
                        token = val
                        logging.info("CAPTCHA manually solved successfully!")
                        if session is not None:
                            try:
                                for cookie in context.cookies():
                                    session.cookies.set(cookie['name'], cookie['value'])
                                logging.info("Transferred Playwright cookies to requests session.")
                            except Exception as e:
                                logging.error(f"Failed to transfer cookies: {e}")
                        break
                except Exception:
                    pass
                time.sleep(2)
                
            browser.close()
            
            if not token:
                logging.error("Manual Captcha solving timed out.")
                
            return token
