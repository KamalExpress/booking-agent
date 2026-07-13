# Token Quickstart

# [#](#token-quickstart)Token Quickstart

### [#](#sending-captcha-sitekey-and-url-and-getting-back-captcha-tokens)Sending CAPTCHA sitekey and URL and getting back CAPTCHA tokens.

-   Pros
    
    No browser required.
    
    No proxies required.
    
-   Cons
    
    Some coding required.
    
    Slower and more costly.
    
    May be detected on some sites.
    

---

## [#](#official-nopecha-libraries)Official NopeCHA libraries

Python Client

https://nopecha.com/pypi

[](https://nopecha.com/pypi)

Node.js Client

https://nopecha.com/npm

[](https://nopecha.com/npm)

---

## [#](#example-code-using-client-libraries)Example code using client libraries

[Python](#python)

[Node.js](#nodejs)

`# Install the client using the following command: # pip install --upgrade nopecha  import nopecha nopecha.api_key = 'YOUR_API_KEY'  # Call the Token API token = nopecha.Token.solve(     type='turnstile',     sitekey='0x4AAAAAAAA-1LUipBaoBpsG',     url='https://nopecha.com/demo/turnstile',     data={         'action': 'login',         'cdata': '0000-1111-2222-3333-example-cdata',     },     proxy={         'scheme': 'http',         'host': '131.171.136.193',         'port': '7234',         'username': 'EhV1AVUbhK',         'password': 'DJ96p39v9z',     } )  # Print the token print(token)`

---

## [#](#example-code-with-minimal-dependencies)Example code with minimal dependencies

[Python](#python)

[JavaScript](#javascript)

Request

Response

`API = 'https://api.nopecha.com/token'  job_id = requests.post(API, json={     'type': 'recaptcha2',     'sitekey': 'b4c45857-0e23-48e6-9017-e28fff99ffb2',     'url': 'https://nopecha.com/demo/recaptcha2',     'key': KEY, }).json()['data']  requests.get(f"{API}?key={KEY}&id={job_id}").json()`

`{     'data': 'P0_eyJ...7mbPUw'  # reCaptcha2 token }`