# Sprint 3: SaaS Dashboard Restructure

**Objective:** Decouple the monolithic SaaS dashboard into a multi-page, modular UI that exposes the new scheduling constructs.

## DAG Tasks
1. [x] **Task 3.1: Dashboard Base Template**
   - **Details:** Create a `base.html` Jinja2 template containing the sidebar navigation (Overview, Workers, Assignments, Logs) and global layout styling.
   - **Dependencies:** Task 1.6

2. [x] **Task 3.2: Overview Page (`/`)**
   - **Details:** High-level metrics. Count of active workers, total active assignments, recent slot discoveries.
   - **Dependencies:** Task 3.1

3. [x] **Task 3.3: Workers Page (`/workers`)**
   - **Details:** Tabular grid listing all `WorkerNode` entries. Show `worker_id`, `labels`, `version`, `status`, `last_heartbeat` (e.g., green dot if < 60s ago, red if dead), and any active leases they hold.
   - **Dependencies:** Task 3.1

4. [x] **Task 3.4: Assignments Page (`/assignments`)**
   - **Details:** Admin interface to CRUD `Assignment` entries. Link them to target `ScraperAccount`s and set required `labels`. Show if they are currently Leased and to which Worker.
   - **Dependencies:** Task 3.1

5. [x] **Task 3.5: Real-time Event Logs Page (`/logs`)**
   - **Details:** A streaming (or polling) view of the `EventLog` table. Color code by `severity` (e.g., Red for `RATE_LIMIT` or `BANNED`, Green for `SLOT_FOUND`, Gray for `LOGIN_SUCCESS`). Allow filtering by `worker_id` or `assignment_id`.
   - **Dependencies:** Task 3.1, Task 2.5 (from Sprint 2)

---
## Execution Notes
- **Outcome**: Successfully decommissioned the 45KB monolithic `index.html` file and split it into clean, modular Jinja2 templates (`base.html`, `index.html`, `workers.html`, `assignments.html`, `logs.html`).
- **Styling**: Kept the same premium dark mode aesthetic (Tailwind + Glassmorphism) requested by the user, now dynamically hydrated with SQLAlchemy context on the server side via `ui.py`.
- **Routing Integration**: Shifted the FastAPI static mounts to `/static` so that `ui.py` can cleanly control the root path `/` and other UI URLs without collisions.
