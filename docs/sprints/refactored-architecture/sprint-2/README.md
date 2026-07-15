# Sprint 2: SaaS Scheduler APIs

**Objective:** Implement the core API endpoints that Workers will use to authenticate, fetch assignments, report events, and renew leases.

## DAG Tasks
1. [x] **Task 2.1: Worker Authentication (`POST /api/v1/worker/register`)**
   - **Details:** 
     - Input: Hardware stats, Location, Capabilities (Labels), Version.
     - Action: Create a new `WorkerNode` in DB, generate a random `secret`.
     - Output: Return `worker_id` and `secret`.
   - **Dependencies:** Task 1.6 (from Sprint 1)

2. [x] **Task 2.2: HMAC Authentication Middleware**
   - **Details:** Implement a FastAPI dependency/middleware that intercepts `/api/v1/worker/*` routes and verifies the HMAC-SHA256 signature using the Worker's secret.
   - **Dependencies:** Task 2.1

3. [x] **Task 2.3: Heartbeat & Lease Renewal (`POST /api/v1/worker/heartbeat`)**
   - **Details:** 
     - Input: CPU, RAM, Running Assignments.
     - Action: Update `WorkerNode.last_heartbeat`. If the worker has active Leases, extend their `expires_at` by N seconds.
   - **Dependencies:** Task 2.2

4. [x] **Task 2.4: Scheduler Scoring Engine (`GET /api/v1/worker/assignments/next`)**
   - **Details:** 
     - Query all idle Assignments (not currently leased).
     - Calculate scores for each Assignment against the requesting Worker (e.g. +100 for `preferred_worker_id == worker_id`, +15 if same country label).
     - Pick the highest-scored Assignment. Create a `Lease` for it.
     - Return the Assignment payload.
     - If no Assignments available, return `204 No Content` with a `Retry-After: 30` header.
   - **Dependencies:** Task 2.3

5. [x] **Task 2.5: Event Ingestion (`POST /api/v1/worker/assignments/{id}/event`)**
   - **Details:** 
     - Input: Event type, Severity, Payload.
     - Action: Insert into `EventLog`. Trigger existing Push Notifications (Telegram, Email, WebPush) if `event_type == 'SLOT_FOUND'`.
   - **Dependencies:** Task 2.2

---
## Execution Notes
- **Outcome**: The `worker.py` FastAPI router was successfully constructed and included in `main.py`.
- **HMAC Auth**: Developed the `verify_worker_hmac` dependency. It verifies timestamps to prevent replay attacks, reconstructs the request body, and strictly enforces HMAC-SHA256 signatures against the worker's unique secret.
- **Lease Scoring**: The `/assignments/next` endpoint dynamically drops expired leases globally before evaluating the best idle assignment for the requesting worker (boosting scores if `preferred_worker_id` matches). It successfully leverages HTTP `204 No Content` with `Retry-After: 30` headers.
- **Eventing**: Event ingestion captures granular JSON logs with severity natively linked to both Worker and Assignment instances.
