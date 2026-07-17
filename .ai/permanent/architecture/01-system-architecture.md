# System Architecture: The Control Plane / Execution Plane Split

## Purpose
To orchestrate distributed headless workers for visa appointment scraping while shielding the central SaaS from WAF (Web Application Firewall) bans.

## Responsibilities
- **Cloud SaaS (Control Plane):** Orchestrates tasks, manages billing, tenants, UI dashboards, and push notifications. It **never** touches the external Visa portals.
- **Headless Workers (Execution Plane):** Distributed nodes (Windows, Linux, Mini PCs) that execute browser automation, bypass captchas, maintain session trust, and report findings back to the SaaS.

## Public Interfaces
- `POST /api/worker/login`
- `POST /api/worker/slots`
- `POST /api/worker/heartbeat`
- `POST /api/worker/log`

## Dependencies
- PostgreSQL (SaaS Storage)
- Web Push API (SaaS Notifications)
- CapSolver / NopeCha (Worker Captcha)
- Playwright / curl_cffi (Worker Orchestration)

## Invariants
- The SaaS must never initiate HTTP requests to the Visa portals. All automation must occur on the workers.
- Workers must pull assignments (polling), the SaaS does not push connections to the workers (allowing workers to sit behind NATs/Firewalls).

## Failure Modes
- **Worker Disconnect:** The SaaS will mark the worker offline if no heartbeat is received, and re-queue its assignment.
- **WAF Block:** The worker will log a 403, drop the session, and re-authenticate using a fresh `curl_cffi` TLS fingerprint.

## Extension Points
- Can deploy workers on residential proxies, AWS workspaces, or Raspberry Pis seamlessly because the API is standard HTTP polling.

## Related ADRs
- `ADR-001 EventLog Telemetry`
- `ADR-002 Polling over WebSockets`
- `ADR-003 curl_cffi for WAF Bypass`

## Related Source Directories
- `ttttt/cloud-saas/app/routers/worker.py`
- `ttttt/operator-agent/main.py`

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
