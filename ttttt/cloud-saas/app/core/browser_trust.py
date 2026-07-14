import os
import time
import logging
from typing import Dict, Optional

class BrowserTrustService:
    """
    Manages the full browser authentication lifecycle using Playwright.
    Ensures that Incapsula/Imperva JS challenges are executed naturally,
    solves Captchas natively within the page, and clicks the submit button
    so the browser natively authenticates and establishes trust cookies.
    """
    def __init__(self, captcha_api_key: str):
        self.captcha_api_key = captcha_api_key
        self.base_url = "https://pk-gr-services.gvcworld.eu"
        
    def authenticate(self, username: str, password: str, sitekey: str) -> Optional[Dict]:
        """
        Runs the full headless authentication flow.
        Returns a dictionary of cookies (cookie jar) if successful, None otherwise.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logging.error("Playwright is not installed. Please install it.")
            return None

        logging.info(f"[BrowserTrust] Starting authentication flow for {username}")
        
        with sync_playwright() as p:
            # We run headless=True so it works seamlessly on VPS
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720}
            )
            
            page = context.new_page()
            
            try:
                # Apply stealth mode to bypass Incapsula headless bot detection
                try:
                    from playwright_stealth import Stealth
                    Stealth().apply_stealth_sync(page)
                except ImportError:
                    # Fallback for older versions if they happen to be installed
                    from playwright_stealth import stealth_sync
                    stealth_sync(page)
                
                # 1. Navigate to the page
                logging.info(f"[BrowserTrust] Navigating to {self.base_url}/login...")
                # We don't use networkidle because Incapsula interstitial might trigger it early.
                page.goto(f"{self.base_url}/login", timeout=30000)
                
                # Wait explicitly for the login form to appear (Incapsula might take several seconds to redirect)
                logging.info("[BrowserTrust] Waiting for Incapsula challenge to clear (if any) and login form to appear...")
                username_selector = 'input[name="username"], input[type="email"], input[id*="user"]'
                page.wait_for_selector(username_selector, timeout=30000)
                
                # 2. Fill credentials naturally
                logging.info("[BrowserTrust] Filling credentials...")
                page.fill(username_selector, username)
                page.fill('input[name="password"], input[type="password"], input[id*="pass"]', password)
                
                # 3. Solve Captcha via CapSolver API
                captcha_token = self._solve_capsolver(sitekey, page.url)
                if not captcha_token:
                    logging.error("[BrowserTrust] Failed to acquire CapSolver token.")
                    return None
                    
                logging.info("[BrowserTrust] Injecting Captcha token into the page...")
                # 4. Inject CapSolver token exactly as the user would solve it
                # Inject into the hidden g-recaptcha-response textarea
                page.evaluate(f'''
                    const textarea = document.getElementById('g-recaptcha-response');
                    if (textarea) {{
                        textarea.innerHTML = '{captcha_token}';
                        textarea.value = '{captcha_token}';
                    }}
                ''')
                
                # 5. Click the "Sign In" / Login button naturally
                logging.info("[BrowserTrust] Clicking login button natively...")
                
                # Trigger click. We wait for either a network response or a successful navigation
                # In many SPAs it might just make an API call, or it might navigate.
                # We'll wait for the network idle state or a specific success indicator.
                with page.expect_response(lambda response: "/api/v1/auth/login" in response.url, timeout=15000) as response_info:
                    # Generic selector that targets typical login buttons
                    page.click('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")')
                
                response = response_info.value
                if response.status == 200:
                    logging.info(f"[BrowserTrust] Authentication Successful! Status: {response.status}")
                else:
                    logging.error(f"[BrowserTrust] Authentication Failed. Status: {response.status}")
                    return None
                
                # Wait briefly to ensure any post-login cookies or local storage finishes updating
                page.wait_for_timeout(2000)
                
                # 6. Export the authenticated cookie jar
                cookies = context.cookies()
                cookie_jar = {}
                for cookie in cookies:
                    cookie_jar[cookie['name']] = cookie['value']
                    
                logging.info(f"[BrowserTrust] Successfully exported {len(cookies)} cookies (including WAF and Auth tokens).")
                return cookie_jar
                
            except Exception as e:
                logging.error(f"[BrowserTrust] Error during browser flow: {e}")
                try:
                    # Dump the HTML for debugging bot protection issues
                    html = page.content()
                    dump_path = os.path.join(os.path.dirname(__file__), "..", "..", "logs", f"waf_block_{int(time.time())}.html")
                    os.makedirs(os.path.dirname(dump_path), exist_ok=True)
                    with open(dump_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                    logging.info(f"[BrowserTrust] Dumped WAF/Error HTML to {dump_path}")
                except Exception as dump_err:
                    logging.error(f"[BrowserTrust] Could not dump HTML: {dump_err}")
                return None
            finally:
                browser.close()

    def _solve_capsolver(self, sitekey: str, url: str) -> str:
        """
        Directly interacts with CapSolver API to fetch the token.
        """
        import requests
        
        logging.info(f"[BrowserTrust] Submitting CapSolver job for {sitekey} on {url}...")
        create_url = "https://api.capsolver.com/createTask"
        payload = {
            "clientKey": self.captcha_api_key,
            "task": {
                "type": "ReCaptchaV2TaskProxyless",
                "websiteURL": url,
                "websiteKey": sitekey
            }
        }
        
        res = requests.post(create_url, json=payload).json()
        if res.get("errorId") != 0:
            logging.error(f"[BrowserTrust] CapSolver creation failed: {res}")
            return ""
            
        task_id = res.get("taskId")
        logging.info(f"[BrowserTrust] Task ID: {task_id}. Polling for completion...")
        
        for _ in range(50):
            time.sleep(3)
            poll_res = requests.post("https://api.capsolver.com/getTaskResult", json={
                "clientKey": self.captcha_api_key,
                "taskId": task_id
            }).json()
            
            status = poll_res.get("status")
            if status == "ready":
                return poll_res.get("solution", {}).get("gRecaptchaResponse", "")
            elif status == "failed":
                logging.error(f"[BrowserTrust] Task failed: {poll_res.get('errorDescription')}")
                return ""
                
        return ""
