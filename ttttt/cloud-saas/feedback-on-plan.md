Based on everything you've shown so far, I would **not** implement Option 2 first. The evidence points toward Option 1 being the correct architectural direction.

Here's why.

### Your desktop application already proved the winning sequence

The successful flow wasn't:

```
requests GET
→ CapSolver
→ requests POST
```

It was effectively:

```
Playwright launches Chromium
        ↓
Incapsula JS executes
        ↓
Browser receives anti-bot cookies
        ↓
reCAPTCHA loads
        ↓
CapSolver solves reCAPTCHA
        ↓
Browser establishes trusted session
        ↓
Requests session inherits cookies
        ↓
API polling
```

That's a fundamentally different trust model.

---

## The cloud logs support this

Cloud:

```
CapSolver solved successfully.
↓
403
↓
Incapsula incident page
```

Notice what's missing.

There is **never** any indication that the server accepted the browser.

The CAPTCHA wasn't rejected.

The login was rejected **before** authentication was trusted.

That strongly suggests the WAF wanted browser state, not merely a valid reCAPTCHA token.

---

## Option 2 is probably insufficient

Doing

```
GET /login
sleep(2)
POST /login
```

only works if Incapsula issues everything from HTTP headers.

Enterprise WAFs often don't.

They frequently require:

* JavaScript execution
* Browser fingerprint generation
* Timing checks
* Local JS computations
* Cookie creation through JS

`curl_cffi` cannot execute JavaScript.

It can impersonate Chrome's TLS.

Those are different things.

---

## Option 1 matches reality

Your desktop already demonstrated that Playwright can satisfy the WAF.

So instead of asking:

> "How do we trick the VPS into looking like Chrome?"

you're asking:

> "How do we reuse the exact browser that already works?"

That's a much stronger approach.

---

# I would make one important change, however.

I would **not** do this:

```
Playwright
↓

transfer cookies

↓

requests.Session

↓

login POST
```

Instead, I'd make the browser responsible for the **entire login**.

```
Playwright
↓

GET login

↓

Incapsula JS

↓

Cookies

↓

CapSolver token

↓

Inject token

↓

Submit login

↓

Authenticated browser

↓

Export cookies

↓

requests.Session

↓

REST API polling only
```

That gives the WAF zero opportunity to complain about a suspicious login POST coming from a different HTTP client.

Once you're authenticated, the REST API polling can continue with `requests` or `curl_cffi`, because you've already observed on the desktop that API calls work perfectly after login.

---

## Even better architecture

I would separate login into its own component.

```
BrowserAuthenticator
    ↓
Playwright Chromium
    ↓
Incapsula
    ↓
reCAPTCHA
    ↓
Login
    ↓
Authenticated cookies
```

Then

```
CookieSession
    ↓
requests / curl_cffi
    ↓
poll slots every 5 minutes
```

Advantages:

* Browser starts only when needed.
* Browser isn't kept running continuously.
* Cookies can be refreshed when they expire.
* Easy to reuse in the future SaaS.

---

## This also future-proofs the SaaS

Later you'll likely support multiple visa portals.

Instead of baking login logic into the monitor:

```
GVC BrowserAuthenticator
TLS BrowserAuthenticator
VFS BrowserAuthenticator
BLS BrowserAuthenticator
```

Each returns

```
AuthenticatedSession
```

The monitoring engine then becomes completely portal-agnostic.

---

## One more thing I would add

Have the authenticator collect diagnostics every time it logs in:

```
Login Diagnostics

✓ Browser launched
✓ Incapsula cookies received
✓ visid_incap
✓ incap_ses
✓ reCAPTCHA loaded
✓ CapSolver token accepted
✓ Login POST 200
✓ Session cookie received
✓ Cookies exported
```

If login ever fails, you'll immediately know **which stage** broke, rather than just seeing a generic `403`.

---

### My recommendation

1. **Use Playwright as the login engine.**
2. **Let Playwright perform the complete login, not just fetch cookies.**
3. **Export the authenticated cookies into a lightweight HTTP client (`requests` or `curl_cffi`) for subsequent slot polling.**
4. **When the session expires, repeat the Playwright login flow.**

That architecture most closely matches the behavior your successful desktop monitor has already demonstrated, minimizes browser runtime, and gives you a clean foundation for the multi-tenant cloud service.
