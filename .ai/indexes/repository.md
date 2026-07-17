# Repository Index

This index maps high-level architectural concepts to their actual source code locations, related documentation, and ADRs.

## SaaS Backend (Control Plane)

### 1. Scheduler / API Routes
- **Implementation:** `ttttt/cloud-saas/app/routers/`
- **Documentation:** `.ai/permanent/architecture/01-system-architecture.md`
- **Related ADRs:** `ADR-001 Polling over WebSockets`
- **Related Workflows:** `worker-registration`, `assignment-fetching`

### 2. Database Models
- **Implementation:** `ttttt/cloud-saas/app/models.py`
- **Documentation:** `.ai/permanent/architecture/02-database.md`
- **Related ADRs:** `ADR-002 EventLog Telemetry`

---

## Worker Node (Execution Plane)

### 3. Worker Lifecycle & Registration
- **Implementation:** `ttttt/operator-agent/main.py`
- **Documentation:** `.ai/permanent/architecture/03-worker-lifecycle.md`
- **Related ADRs:** `ADR-003 Capability-based Routing`

### 4. Browser Trust (Captcha Solving)
- **Implementation:** `ttttt/operator-agent/core/browser_trust.py`
- **Documentation:** `.ai/permanent/architecture/04-browser-orchestration.md`
- **Related ADRs:** `ADR-004 Playwright for Recaptcha V2`
- **Lessons:** `.ai/lessons/imperva-tls-fingerprint.md`

### 5. API Client (WAF Evasion)
- **Implementation:** `ttttt/operator-agent/core/session_manager.py` (Using `curl_cffi`)
- **Documentation:** `.ai/permanent/architecture/05-network-layer.md`
- **Related ADRs:** `ADR-005 curl_cffi for WAF Bypass`
- **Lessons:** `.ai/lessons/imperva-tls-fingerprint.md`

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
