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

## Future Notes
- Any external request to the visa portals must be routed through the `curl_cffi` SessionManager. Do not import `requests` in the worker codebase.
- If 403s return, the impersonation string might need to be upgraded to a newer Chrome/Edge version in `session_manager.py`.

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
