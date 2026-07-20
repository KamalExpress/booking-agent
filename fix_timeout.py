import sys
with open('ttttt/operator-agent/main_operator.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                # Navigate to the login page (without networkidle, as tracking scripts can prevent it)
                logging.info(f"Navigating to {self.base_url}/login to clear WAF...")
                page.goto(f"{self.base_url}/login", timeout=30000)
                
                # Wait for the username input box to appear. This guarantees Imperva has fully cleared us.
                logging.info("Waiting for Imperva JS challenge to clear and login form to render...")
                username_selector = 'input[name="username"], input[type="email"], input[id*="user"]'
                page.wait_for_selector(username_selector, timeout=30000)'''

replacement = '''                # Navigate to the login page (without networkidle, as tracking scripts can prevent it)
                logging.info(f"Navigating to {self.base_url}/login to clear WAF...")
                # Use wait_until="commit" so Playwright doesn't wait for the extremely slow WAF assets to fully 'load'
                page.goto(f"{self.base_url}/login", wait_until="commit", timeout=60000)
                
                # Wait for the username input box to appear. This guarantees Imperva has fully cleared us.
                logging.info("Waiting for Imperva JS challenge to clear and login form to render...")
                username_selector = 'input[name="username"], input[type="email"], input[id*="user"]'
                # Allow up to 90 seconds for the WAF challenge to compute on the slow VPS proxy
                page.wait_for_selector(username_selector, timeout=90000)'''

if target in content:
    content = content.replace(target, replacement)
    with open('ttttt/operator-agent/main_operator.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced successfully')
else:
    print('Target not found')
