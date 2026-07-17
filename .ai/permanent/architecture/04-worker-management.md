# Worker Management & Lease Architecture

## Purpose
To manage the fleet of distributed Worker Nodes, monitor their health, route assignments via durable leases, and maintain system stability statelessly.

## Responsibilities
- **Worker Lifecycle:** Track Worker state (Online, Offline, Disabled, Draining, Maintenance, Blocked, Error) via `WorkerService`.
- **Lease State Machine:** Track historical and active executions (Pending, Leased, Running, Completed, Expired, Cancelled) via `LeaseService`.
- **Automated Maintenance:** Prune dead workers, archive completed leases, and clean up telemetry via `MaintenanceService` continuously without background threads.
- **Proxy Abstraction:** Abstract IP assignments via Proxy Pools during runtime config retrieval.

## Public Interfaces
- `/api/v1/worker/register`: Establishes trust and returns a secret.
- `/api/v1/worker/heartbeat`: Receives health metrics, capabilities, and extends active leases.
- `/api/v1/worker/assignments/next`: Defensively invokes the `MaintenanceService` cleanup cycle before assigning the next best Lease.
- `/api/v1/worker/offline`: Allows graceful worker shutdown without waiting for heartbeat timeouts.

## Dependencies
- PostgreSQL (Lease, LeaseArchive, EventLog, WorkerNode tables).
- Scheduler Engine (Assigns work based on capability matching).
- Worker Nodes (Must honestly report their capabilities and network location).

## Invariants
- Assignments are never statically tied to a specific worker machine. They are tied to a set of required labels (e.g., `country=pk`, `residential=true`).
- Proxy usage is abstracted. Assignments reference a `Proxy Pool` (e.g., "Pakistan Residential"), and the SaaS resolves this into actual proxy credentials sent to the worker at runtime.
- **Durable Leases:** A `Lease` record is never deleted upon completion. It transitions through a state machine and is eventually archived to `LeaseArchive` by the `MaintenanceService`.

## Failure Modes
- **Worker Crash:** The worker stops sending heartbeats. Next time any worker hits `/assignments/next`, the `MaintenanceService` will mark the dead worker `Offline` and `LeaseService` will mark its leases `Expired`, allowing re-assignment.
- **Worker enters `Draining` state:** It finishes its current lease but refuses new assignments (useful for seamless deployments).

## Related Source Directories
- `ttttt/cloud-saas/app/services/worker_service.py`
- `ttttt/cloud-saas/app/services/lease_service.py`
- `ttttt/cloud-saas/app/services/maintenance_service.py`
- `ttttt/cloud-saas/app/routers/worker.py`

---
*Last Reviewed: Sprint 10 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
