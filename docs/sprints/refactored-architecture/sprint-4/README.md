# Sprint 4: Worker Node Implementation

**Objective:** Strip the desktop agent (`operator-agent`) of its local database and UI dependencies, wrapping its proven Playwright logic in the new SaaS API Client.

## DAG Tasks
1. [x] **Task 4.1: Rip out Local State Management**
   - **Details:** Remove SQLite dependencies from `operator-agent`. The Worker should be stateless. It no longer needs to store Accounts or API configurations locally.
   - **Dependencies:** Task 2.5 (from Sprint 2)

2. [x] **Task 4.2: Implement SaaS API Client**
   - **Details:** Build a `SaaSClient` in Python. Handles calling `/api/v1/worker/register`, securely storing the `worker_id` and `secret` in memory (or temporary dotfile), spawning a daemon thread for `/heartbeat`, and signing all API calls using HMAC-SHA256.
   - **Dependencies:** Task 4.1

3. [x] **Task 4.3: Main Execution Loop (The Scheduler)**
   - **Details:** The worker's main loop should repeatedly call `GET /api/v1/worker/assignments/next`. If it receives `204 No Content`, it sleeps for the duration specified in the `Retry-After` header.
   - **Dependencies:** Task 4.2

4. [x] **Task 4.4: Adapt Playwright Engine**
   - **Details:** 
     - When an assignment is received, spawn the Playwright/Requests monitoring logic using the credentials from the payload.
     - Replace local file logging with `POST /api/v1/worker/assignments/{id}/event` to stream `LOGIN_SUCCESS`, `RATE_LIMIT`, `SLOT_FOUND` up to the SaaS.
   - **Dependencies:** Task 4.3

5. [x] **Task 4.5: End-to-End Testing**
   - **Details:** Launch the SaaS. Launch a Worker Node. Verify the Worker registers, pulls an Assignment from the DB, executes it, and streams logs back to the SaaS Dashboard.
   - **Dependencies:** Task 4.4

---
## Execution Notes
- **Outcome**: The `operator-agent` is now fully stateless and driven by the central orchestrator! 
- **Code Removal**: Stripped out local `config_manager.py` SQLite logic and all settings tabs from the CustomTkinter `gui.py`. The GUI is now a pure viewer focused solely on pointing to a `SaaS URL` and rendering the execution logs.
- **Worker Logic**: `slot_monitor.py` was rewritten to poll `/assignments/next`. When it grabs a lease, it instantiates `OperatorAgent` with the SaaS-provided credentials, targets the specific date ranges, and pushes events (e.g., `LOGIN_SUCCESS`, `SLOT_FOUND`) back up to the Orchestrator via the HMAC-authenticated `api_client.py`.
