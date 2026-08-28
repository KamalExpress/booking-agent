# Imperva WAF / Cloudflare TLS Fingerprinting

## Problem
During worker execution, the visa portal immediately returned HTTP `403 Forbidden` after solving a Captcha, blocking access to the slot APIs.

## Root Cause
The portal employs Imperva (and potentially Cloudflare) Web Application Firewalls. These firewalls perform deep packet inspection on the TLS handshake. Standard Python libraries like `requests` and `httpx` send TLS `ClientHello` packets that definitively identify them as bots (they are missing modern cipher suites and ALPN extensions present in Chrome/Edge).

## Attempted Solutions

### 1. Python `requests` library
- **Status:** FAILED
- **Reason:** Immediate 403. Cannot spoof TLS fingerprints natively.

### 2. Standard `urllib` / `httpx`
- **Status:** FAILED
- **Reason:** Same fingerprinting issues as `requests`.

### 3. Playwright (Headless Browser)
- **Status:** Rejected for pure API scraping.
- **Reason:** Extremely resource-intensive. Managing hundreds of headless browser tabs across workers will consume excessive RAM and CPU, reducing worker density. (Playwright is still used sparingly just for the initial Captcha solving phase).

### 4. `curl_cffi` (impersonate="chrome110")
- **Status:** SUCCESS
- **Reason:** Uses a compiled C backend (`curl-impersonate`) to perfectly mimic the TLS `ClientHello` packets, HTTP/2 frames, and header ordering of a genuine Chrome 110 browser. The WAF accepts the connection.

## 5. Imperva JS Challenge & Cookie Expiration (WAF Tarpit)
- **Problem:** Even with a perfect TLS fingerprint, `curl_cffi` cannot execute Javascript. Imperva occasionally issues a JS challenge (`/_Incapsula_Resource`) that must be executed to generate advanced trust cookies (e.g., `___utmvc`, `incap_ses_*`). If these cookies expire (typically after 24-30 hours) or are missing, Imperva silently **tarpits** (drops) all `POST` requests without sending a TCP reset, causing a `curl: (28) Operation timed out` error after 30 seconds.
- **Solution (Playwright Handoff):** The headless worker automatically detects the `(28)` timeout and spawns a hidden, headless Playwright instance for 10 seconds. Playwright natively executes the JS challenge, extracts the fresh cookie jar, and injects it back into `curl_cffi`. 
- **CRITICAL CONSTRAINT:** The Playwright `user_agent` and `sec-ch-ua` headers **MUST EXACTLY MATCH** the impersonated browser in `curl_cffi` (e.g., macOS Chrome 120). If Playwright uses a different fingerprint to solve the JS challenge, Imperva detects the mismatch during the `curl_cffi` handoff and immediately blocks the request with a `403 Forbidden`.

## 6. Imperva Rule B10: Header Anomaly & HTTP 200 Interception
- **Symptom:** Worker login or pre-flight request returns **HTTP 200 OK** with a 212-byte HTML body containing:
  ```html
  <html><head><META NAME="robots" CONTENT="noindex,nofollow">
  <script src="/_Incapsula_Resource?SWJIYLWA=..."></script></head><body></body></html>
  ```
  In the response headers, `x-iinfo` contains `B10(...)` (e.g., `B10(11,19913348,0)`).
- **Root Cause:** In Imperva's internal diagnostics, `B10` designates **"Bot Detection Rule 10: Inconsistent / Impossible Browser Header Signature"**. It triggers when request headers contain contradictory or non-browser behavior:
  1. Sending `Origin` on a top-level `GET` document navigation (`Sec-Fetch-Dest: document`). A real browser **never** sends `Origin` on a `GET` navigation.
  2. Sending `Accept: application/json` on a top-level document navigation instead of `text/html,application/xhtml+xml,...`.
  3. Setting `Sec-Fetch-Site: same-origin` instead of `none` on address-bar navigations.
  4. Missing `Upgrade-Insecure-Requests: 1` or `Sec-Fetch-User: ?1`.
- **Resolution:**
  - On `GET /?lang=en_US`: Explicitly strip `Origin` and `X-Requested-With`, set `Accept: text/html...`, `Sec-Fetch-Site: none`, `Sec-Fetch-User: ?1`, and `Upgrade-Insecure-Requests: 1`.
  - Once header anomalies are resolved, Imperva passes the request upstream to the portal without triggering `B10`.

## 7. Endpoint-Specific Invariants (Referer & Content-Type)
- **Login (`POST /api/v1/auth/login`):**
  - `Referer` MUST be `https://<domain>/login` (not the portal root `/?lang=en_US`).
  - `Content-Type` MUST be `application/json; charset=UTF-8`.
- **Slot Availability (`PUT /api/v1/periodslot/slots`):**
  - In a real browser, slot availability is checked strictly from the appointment booking form. `Referer` MUST be `https://<domain>/appointments/add`.
  - `Accept` MUST be `*/*`.
  - `Content-Type` MUST be `application/json; charset=UTF-8`.

## 8. GVC Authentication Response Structure
- **Empty Body on Success:** GVC's `POST /api/v1/auth/login` returns **HTTP 200 OK with an empty body** (`content-length: 0`).
- **Token Delivery:** The JWT token is returned in the `authorization: Bearer <jwt_token>` response header and as a `set-cookie: auth_token=<jwt_token>` cookie.
- **Worker Configuration:** The worker must extract the token from headers or cookies and attach it as `Authorization: Bearer <jwt_token>` to all subsequent requests. If absent, subsequent API calls will silently fail or redirect.

## 9. Operational Calendar Scheduling (Weekend Exclusion)
- **Weekend Invariant:** Visa Application Centers (VACs) across Pakistan (Lahore VAC 137, Islamabad VAC 138) are **strictly closed on weekends (Saturday & Sunday)**.
- **Rule:** Date generation logic (`slot_monitor.py` and `core/slot_monitor.py`) must enforce `weekday < 5` (Monday=0 through Friday=4).
- **Type D Visa (Code 26):** For Greece Type D Seasonal / Dependent Employment (code `26`), embassy slots operate exclusively on **Thursday (3) and Friday (4)**.
- **Impact:** Eliminates wasted CAPTCHA tokens, saves proxy egress bandwidth, and avoids triggering rate limits on days when centers are 100% known to be closed.

## 10. Future Notes
- Any external request to the visa portals must be routed through the `curl_cffi` SessionManager. Do not import `requests` in the worker codebase.
- Session persistence (`load_session`) must support both JSON and legacy Python `pickle` formats to avoid invalidating sessions on container restarts.

---
*Last Reviewed: August 29, 2026 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
