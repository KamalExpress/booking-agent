# Worker Management Architecture

## Purpose
To manage the fleet of distributed Worker Nodes, monitor their health, and route assignments to them intelligently.

## Responsibilities
- Track Worker state (Online, Offline, Disabled, Draining, Maintenance, Blocked, Error).
- Abstract IP assignments via Proxy Pools.
- Route assignments using Capability-based Scheduling (matching required capabilities to worker capabilities).

## Public Interfaces
- `/api/worker/heartbeat`: Receives health metrics, capabilities, and IP location from the worker.
- `/api/worker/runtime-config`: Provides the worker with assigned proxy credentials.

## Dependencies
- Scheduler Engine (Assigns work based on capability matching).
- Worker Nodes (Must honestly report their capabilities and network location).

## Invariants
- Assignments are never statically tied to a specific worker machine. They are tied to a set of required labels (e.g., `country=pk`, `residential=true`).
- Proxy usage is abstracted. Assignments reference a `Proxy Pool` (e.g., "Pakistan Residential"), and the SaaS resolves this into actual proxy credentials sent to the worker at runtime.

## Failure Modes
- Worker goes offline during a lease: Lease expires naturally and the Scheduler reassigns the work to another capable worker.
- Worker enters `Draining` state: It finishes its current lease but refuses new assignments (useful for seamless deployments).

## Extension Points
- Can add more capabilities (e.g., `gpu=true`, `browser=firefox`) as worker variations grow.

## Related Source Directories
- `ttttt/cloud-saas/app/routers/worker.py`

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
