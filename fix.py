import sys
with open('ttttt/operator-agent/main_operator.py', 'r', encoding='utf-8') as f:
    content = f.read()

target2 = '''                # Extract and inject cookies
                cookies = context.cookies()
                for cookie in cookies:
                    try:
                        self.session.cookies.delete(cookie['name'])
                    except Exception:
                        pass
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', 'pk-gr-services.gvcworld.eu'))'''

replacement2 = '''                # Extract and inject cookies
                cookies = context.cookies()
                self.session.cookies.clear() # Completely wipe the old tainted cookie jar
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', 'pk-gr-services.gvcworld.eu'))'''

if target2 in content:
    content = content.replace(target2, replacement2)
    with open('ttttt/operator-agent/main_operator.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced successfully')
else:
    print('Target not found')
