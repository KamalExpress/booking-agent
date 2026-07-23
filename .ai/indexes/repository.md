# Repository Index

This index maps high-level architectural concepts to their actual source code locations, related documentation, and ADRs.

## SaaS Backend (Control Plane)

### 1. Scheduler & API Routing
- **Implementation:** `ttttt/cloud-saas/app/routers/`
- **Documentation:** `.ai/permanent/architecture/01-system-architecture.md`
- **Related ADRs:** `ADR-001 Polling over WebSockets`
- **Related Workflows:** `worker-registration`, `assignment-fetching`, `booking-task-dispatch`

### 2. Service Layer (Business Logic & Maintenance)
- **Implementation:** `ttttt/cloud-saas/app/services/`
  - `worker_service.py`: Lifecycle, heartbeat.
  - `scheduler_service.py`: Waitlist auto-dispatch, assignment matching.
  - `scoring_policy.py`: Account and Proxy rating systems.
  - `lease_service.py`: State machine, lease validation.
  - `maintenance_service.py`: Defensive cleanup, archiving.
- **Documentation:** `.ai/permanent/architecture/04-worker-management.md`

### 3. Database Models & Telemetry
- **Implementation:** `ttttt/cloud-saas/app/models.py`
- **Documentation:** `.ai/permanent/architecture/02-database.md`
- **Related ADRs:** `ADR-002 EventLog Telemetry`

### 4. Frontend UI / Dashboard (PWA)
- **Implementation:** `ttttt/cloud-saas/static/` and `ttttt/cloud-saas/app/templates/` (Unified SaaS Admin & Tenant Dashboard)
- **Note:** The frontend uses Jinja templates embedded directly within the SaaS backend repository. There is no separate frontend repo.

---

## Worker Node (Execution Plane)

### 4. Worker Lifecycle & Registration
- **Implementation:** `ttttt/operator-agent/headless.py` (Scraping engine) and `ttttt/operator-agent/headless_booker.py` (Booking engine)
- **Documentation:** `.ai/permanent/architecture/03-worker-lifecycle.md`
- **Related ADRs:** `ADR-003 Capability-based Routing`

### 5. Browser Trust (Captcha Solving)
- **Implementation:** `ttttt/operator-agent/core/browser_trust.py`
- **Documentation:** `.ai/permanent/architecture/04-browser-orchestration.md`
- **Related ADRs:** `ADR-004 Playwright for Recaptcha V2`
- **Lessons:** `.ai/lessons/imperva-tls-fingerprint.md`

### 6. API Client (WAF Evasion)
- **Implementation:** `ttttt/operator-agent/api_client.py` and `ttttt/operator-agent/core/session_manager.py` (Using `curl_cffi`)
- **Documentation:** `.ai/permanent/architecture/05-network-layer.md`
- **Related ADRs:** `ADR-005 curl_cffi for WAF Bypass`
- **Lessons:** `.ai/lessons/imperva-tls-fingerprint.md`

### 7. Extraction Engines
- **Implementation:** `ttttt/operator-agent/slot_monitor.py` (Slot parsing and target matching)
- **Note:** Worker instances run inside separate docker containers.

---

## Testing & Automation

### 8. End-to-End (E2E) Testing
- **Implementation:** `testing-procedure/keagent-e2e-tests/`
- **Documentation:** `.ai/transient/sprint/05-e2e-coverage.md`
- **Note:** Uses Playwright for tenant workflow testing and background verification.

---
*Last Reviewed: Sprint 11 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
