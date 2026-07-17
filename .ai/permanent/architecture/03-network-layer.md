# Network Layer (WAF Evasion)

## Purpose
To execute HTTP requests against external visa portals while evading sophisticated Web Application Firewalls (e.g., Imperva, Cloudflare, Akamai).

## Responsibilities
- Mimic genuine browser TLS fingerprints.
- Handle cookies, redirects, and headers exactly as a modern browser would.
- Serve as the foundation for the `SessionManager` in the headless worker.

## Public Interfaces
- `SessionManager.get_session()`
- `SessionManager.get()`
- `SessionManager.post()`

## Dependencies
- `curl_cffi` (Underlying library impersonating Chrome/Edge).

## Invariants
- **NEVER** use the standard Python `requests` library for external requests. It will result in immediate 403 blocks due to its well-known TLS fingerprint.

## Failure Modes
- **403 Forbidden:** The WAF has detected automation. The worker must drop the session, initialize a new `curl_cffi` session with a fresh proxy IP and User-Agent, and solve a new Captcha.

## Extension Points
- Can be extended to support proxy rotation automatically if a 403 is hit.

## Related ADRs
- `ADR-003 curl_cffi for WAF Bypass`

## Related Source Directories
- `ttttt/operator-agent/core/session_manager.py`

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
