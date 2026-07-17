# ADR-005: Billing Metrics via Event Sourcing

## Status
Experimental / Deferred

## Context
The SaaS control plane requires telemetry to build billing quotas (e.g., tracking how many GBs of proxy bandwidth are used, and how many Captchas are solved/failed per Tenant).
The original thought was to have the workers log this explicitly via a new API endpoint (`/api/worker/metrics`).

## Decision
We have decided **against** building telemetry aggregation into the headless workers. 
The workers must remain "thin" and stateless. Adding logic to buffer request bytes and captcha counts introduces memory bloat and violates their single responsibility (executing assignments).

Instead, we will rely on the native dashboards provided by Decodo (proxies) and CapSolver (captchas) for the time being. If in-house metrics become strictly necessary, we will implement an Event Sourcing mechanism (e.g., streaming raw events to a message broker) rather than batch-logging from the worker.

## Consequences
- **Positive:** Workers remain extremely lightweight.
- **Positive:** Reduces database writes to the SaaS Postgres instance.
- **Negative:** SaaS Admins cannot view bandwidth metrics natively inside the SaaS dashboard.

## Related Components
- Worker Core
- SaaS Database

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
