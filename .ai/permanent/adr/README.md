# Architecture Decision Records (ADR) Index

This directory stores decisions regarding the architecture, design, and technologies used in the project.

## Index

| ADR ID | Title | Status | Related Components |
|--------|-------|--------|---------------------|
| ADR-001 | [EventLog Telemetry](001-eventlog-telemetry.md) | Accepted | Database, FastAPI, Worker |
| ADR-002 | [Polling over WebSockets](002-polling-over-websockets.md) | Accepted | Scheduler, FastAPI |
| ADR-003 | [curl_cffi for WAF Bypass](003-curl-cffi.md) | Accepted | Network Layer, Worker |
| ADR-004 | [Playwright for Captcha Solving](004-playwright-captcha.md) | Accepted | Browser Trust, Worker |
| ADR-005 | [Billing Metrics via Event Sourcing](005-billing-metrics.md) | Experimental / Deferred | Database, Knowledge Base |

## Status Definitions
- **Accepted:** Actively used in the project.
- **Superseded:** Replaced by a newer ADR.
- **Deprecated:** No longer used or relevant.
- **Experimental:** Proposed or being tested, not yet fully integrated.
- **Rejected:** Considered but ultimately not implemented (highly valuable for historical context).

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
