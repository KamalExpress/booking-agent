from curl_cffi import requests

print("Testing with curl_cffi (Chrome 120)...")
session = requests.Session(impersonate="chrome120")

# Simulate exactly what the bot would do: 
# 1. GET /login to grab initial Incapsula cookies
response_get = session.get("https://pk-gr-services.gvcworld.eu/login")
print("GET Status:", response_get.status_code)
print("GET Cookies:", session.cookies.get_dict())

if "_Incapsula_Resource" in response_get.text:
    print("WARNING: Incapsula JS challenge detected on GET!")
else:
    print("SUCCESS: Clean HTML received on GET!")

# 2. Try an empty POST to the API just to see if it 403s or 401s (Unauth is fine, 403 is WAF block)
response_post = session.post("https://pk-gr-services.gvcworld.eu/api/v1/auth/login", json={})
print("POST Status:", response_post.status_code)
if response_post.status_code == 403:
    print("WARNING: WAF Blocked the POST request!")
else:
    print(f"SUCCESS: WAF did not block the POST! (Status {response_post.status_code})")
