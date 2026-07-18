# Database Architecture

## Purpose
The central storage layer for the Cloud SaaS (Control Plane). It maintains the state of Tenants, Users, Worker Nodes, Assignments, Leases, and System Logs.

## Responsibilities
- Track Tenant quotas and billing status.
- Manage user granular preferences via JSONB (e.g. `muted_visa_centers`).
- Store Assignments configured by users.
- Track Worker Node heartbeats and IP addresses.
- Issue Leases to workers (locking an Assignment to a specific worker for a set time).
- Persist `EventLog` telemetry (Slot findings, Push notifications, Errors).
- Store dynamically configurable SaaS properties via `SystemSetting` (e.g., PWA toggles).

## Public Interfaces
- Interacted with strictly via SQLAlchemy ORM in the FastAPI app (`app/models.py`).
- No direct database access from Worker Nodes.

## Dependencies
- PostgreSQL (Primary Relational Store)

## Invariants
- A Worker Node cannot access data belonging to another Tenant. (Note: Currently workers pull assignments globally via generic `/api/worker/slots`, but data separation is enforced via `Assignment` relationships).
- A single Assignment can only have one active `Lease` at any given time.

## Failure Modes
- Database Connection Loss: The FastAPI application will return 500s. Workers will catch HTTP errors, back off, and retry later.

## Extension Points
- Can implement read replicas if `EventLog` queries become too heavy.

## Related ADRs
- `ADR-001 EventLog Telemetry`

## Related Source Directories
- `ttttt/cloud-saas/app/models.py`
- `ttttt/cloud-saas/app/database.py`

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
