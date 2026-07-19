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

## Future Notes
- Any external request to the visa portals must be routed through the `curl_cffi` SessionManager. Do not import `requests` in the worker codebase.
- If 403s return, verify that the Playwright configuration in `main_operator.py` identically matches the `curl_cffi` impersonation string.

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
