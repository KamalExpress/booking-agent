import abc
import requests
import time
import logging
import os
import sys

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

        logging.info("Polling for NopeCha completion...")
        for _ in range(40):
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
    def __init__(self, api_key: str, proxy_string: str = None):
        self.api_key = api_key
        self.proxy_string = proxy_string
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
            
            if self.proxy_string:
                from urllib.parse import urlparse
                parsed = urlparse(self.proxy_string)
                payload["task"]["type"] = "ReCaptchaV2Task"
                payload["task"]["proxyType"] = "http"
                payload["task"]["proxyAddress"] = parsed.hostname
                payload["task"]["proxyPort"] = parsed.port
                payload["task"]["proxyLogin"] = parsed.username
                payload["task"]["proxyPassword"] = parsed.password
            
            try:
                res = requests.post(self.create_task_url, json=payload, timeout=15).json()
                if res.get("errorId") != 0:
                    error_code = res.get("errorCode", "")
                    error_desc = res.get("errorDescription", "")
                    logging.error(f"CapSolver creation failed (Code: {error_code}): {error_desc}")
                    
                    if error_code == "ERROR_ZERO_BALANCE":
                        logging.error("CRITICAL: CapSolver service balance is ZERO (ERROR_ZERO_BALANCE). Top-up required immediately!")
                        return ""
                    continue
                
                task_id = res.get("taskId")
                logging.info(f"CapSolver job submitted successfully. Task ID: {task_id}")
                logging.info("Polling for CapSolver completion... (Max 150 seconds)")
                
                poll_start = time.time()
                for poll_count in range(1, 51):
                    time.sleep(3)
                    poll_payload = {
                        "clientKey": self.api_key,
                        "taskId": task_id
                    }
                    poll_res = requests.post(self.get_result_url, json=poll_payload, timeout=15).json()
                    status = poll_res.get("status")
                    elapsed = int(time.time() - poll_start)
                    
                    if status == "ready":
                        token = poll_res.get("solution", {}).get("gRecaptchaResponse", "")
                        logging.info(f"CapSolver solved the CAPTCHA successfully in {elapsed}s! (Token length: {len(token)})")
                        return token
                    elif status == "failed":
                        err_desc = poll_res.get('errorDescription') or poll_res.get('errorCode') or 'Unknown error'
                        logging.error(f"CapSolver task failed ({err_desc}) after {elapsed}s.")
                        break
                    
                    if poll_count % 3 == 0:
                        logging.info(f"Still waiting for CapSolver ({elapsed}s elapsed)... status: {status}")
                    else:
                        logging.debug(f"Waiting for CapSolver... current status: {status}")
                    
                logging.warning(f"CapSolver attempt {attempt} timed out or failed after {int(time.time() - poll_start)}s.")
            except Exception as e:
                logging.error(f"Error during CapSolver job: {e}")
                
        logging.error("CapSolver failed after maximum attempts.")
        return ""

class ManualCaptchaService(CaptchaService):
    def solve(self, sitekey: str, url: str, **kwargs) -> str:
        # Check if headless / server environment
        is_server_env = (
            os.getenv("HEADLESS", "true").lower() in ["true", "1"] or 
            (sys.platform.startswith("linux") and not os.getenv("DISPLAY"))
        )
        if is_server_env:
            logging.warning("ManualCaptchaService: Server is running in headless/Docker mode without GUI display ($DISPLAY). Skipping manual browser launch.")
            return ""

        session = kwargs.get('session')
        logging.info(f"Starting Manual Captcha Solver for {url}...")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logging.error("Playwright is not installed.")
            return ""

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                logging.info("Navigating to the login page...")
                try:
                    page.goto(url, timeout=30000)
                except Exception as e:
                    logging.error(f"Playwright failed to navigate to login page: {e}")
                    browser.close()
                    return ""
                
                username = os.getenv('PORTAL_USERNAME', '')
                password = os.getenv('PORTAL_PASSWORD', '')
                if username and password:
                    try:
                        page.fill('input[name="username"], input[type="email"], input[id*="user"]', username, timeout=2000)
                        page.fill('input[name="password"], input[type="password"], input[id*="pass"]', password, timeout=2000)
                        logging.info("Autofilled username and password in browser.")
                    except Exception:
                        pass
                
                logging.info("Waiting for manual Captcha solving... (300s timeout)")
                print("\n*** PLEASE SOLVE THE CAPTCHA IN THE OPENED BROWSER WINDOW ***\n")
                
                try:
                    import winsound
                    for _ in range(3):
                        winsound.Beep(1000, 500)
                        time.sleep(0.1)
                except Exception:
                    pass
                
                token = ""
                for _ in range(150):
                    try:
                        val = page.evaluate("document.getElementById('g-recaptcha-response') ? document.getElementById('g-recaptcha-response').value : ''")
                        if val and len(val) > 10:
                            token = val
                            logging.info("CAPTCHA manually solved successfully!")
                            if session is not None:
                                try:
                                    for cookie in context.cookies():
                                        session.cookies.set(cookie['name'], cookie['value'])
                                except Exception:
                                    pass
                            break
                    except Exception:
                        pass
                    time.sleep(2)
                    
                browser.close()
                return token
        except Exception as e:
            logging.error(f"ManualCaptchaService encountered error: {e}")
            return ""
