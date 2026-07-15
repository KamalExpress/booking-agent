# Distributed Master-Worker Architecture

The guiding principle for this platform:
> **The SaaS schedules work, but does not understand browsers. The Worker understands browsers, but does not understand scheduling.**

By adhering to this strict boundary, the SaaS transforms into a generic distributed automation platform (capable of managing Visa scrapers, Playwright regression tests, or Odoo QA bots), while the Workers act as stateless, secure execution nodes that isolate all WAF-sensitive browser state.

## Architectural Design

### 1. The Control Plane (Cloud SaaS)
The SaaS operates as a sophisticated job scheduler, managing Assignments, Leases, and Worker Health based on capability labels.

**Database Models to Add/Update:**
- `WorkerNode`: Tracks active workers (`worker_id`, `secret`, `labels` (e.g., `["pakistan", "residential"]`), `version`, `last_heartbeat`, `status`).
- `Assignment`: Represents a monitoring task (Target Account, Date Range, Polling Interval, required labels).
- `Lease`: Binds an `Assignment` to a `WorkerNode` with an explicit expiration time.
- `EventLog`: A generic JSON log mapping: `source`, `worker_id`, `assignment_id`, `severity`, `event_type` (e.g. `RATE_LIMIT`), and a flexible `payload` object.

**Core Worker APIs (`/api/v1/worker/...`):**
- `POST /register`: Worker registers with its hardware capabilities, location, and labels. SaaS returns a unique `WorkerSecret` for HMAC signing.
- `POST /heartbeat`: Worker sends health (CPU/RAM). Crucially, **heartbeats automatically renew active leases**.
- `GET /assignments/next`: Scheduler uses a **scoring algorithm** (e.g., +100 preferred worker, +15 same country, +10 idle worker) to pick the best idle Assignment, create a Lease, and return it. If none exist, returns `204 No Content` with a `Retry-After` header to pace worker requests.
- `POST /assignments/{id}/event`: Ingests operational events (e.g., `LOGIN_SUCCESS`, `SLOT_FOUND`).

### 2. The Execution Plane (Worker Node)
The worker is a generic runtime wrapper around domain-specific "Plugins" (like the Greece Visa script). It never touches the SaaS DB.

**Worker Node Behavior:**
- Authenticates securely via HMAC.
- Enters an execution loop:
  1. Requests work via `GET /assignments/next`. Sleeps if `Retry-After` is received.
  2. If assigned, launches the Visa monitoring logic natively, loading `.pkl` files exactly as it does today. Cookie jars **never** leave the worker.
  3. Spawns a background heartbeat thread that continually renews the lease while the task runs.
  4. Pushes granular, structured events to the SaaS event stream.
- If a worker dies, its heartbeats stop, the SaaS lease expires, and the Scheduler automatically reassigns the task to another capable node.

### 3. SaaS Dashboard Refactor
The SaaS UI transitions from a monolithic page to modular views:
- **Overview**: High-level system stats.
- **Workers**: Live grid of registered workers, their `labels`, `version`, and active leases.
- **Assignments**: Management of required automation tasks.
- **Events (Logs)**: Real-time firehose of structured events.

---

## Proposed Implementation Steps

### Phase 1: Setup & Data Modeling (No Cloning)
1. Delete the `cloud-saas/app/core/slot_monitor.py` (and related WAF components) from the SaaS to enforce the new boundary.
2. Update the `cloud-saas` DB models to match the new `WorkerNode`, `Assignment`, `Lease`, and `EventLog` design.
3. Generate DB migrations.

### Phase 2: SaaS Scheduler APIs
1. Implement worker registration and HMAC authentication.
2. Build the Scoring & Lease Engine for `GET /assignments/next`.
3. Implement the `Retry-After` response header for paced polling.
4. Build the event ingestion and heartbeat/lease-renewal endpoints.

### Phase 3: SaaS Dashboard Restructure
1. Refactor the monolithic SaaS dashboard HTML into modular Jinja templates (Overview, Workers, Assignments, Logs).

### Phase 4: Worker Node Implementation
1. Refactor `operator-agent` in-place to act as the new Worker Node runtime.
2. Strip out all local DB logic and replace it with the generic SaaS API client.
3. Wire the existing Playwright logic to run strictly based on leased Assignments.

---

I am ready to begin Phase 1 as soon as you approve!
