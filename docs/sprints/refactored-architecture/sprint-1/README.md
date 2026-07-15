# Sprint 1: Setup & Data Modeling

**Objective:** Clean up the existing codebase and establish the new Database schemas for the distributed scheduling architecture.

## DAG Tasks
1. [x] **Task 1.1: Move WAF Components from SaaS to Worker**
   - **Details:** Move `cloud-saas/app/core/slot_monitor.py`, `browser_trust.py`, and `session_manager.py` over to the `operator-agent/` directory instead of deleting them, so we retain the code for Sprint 4. Remove the background thread instantiation from `cloud-saas/app/main.py` entirely. The SaaS must not touch the visa portal.
   - **Dependencies:** None

2. [x] **Task 1.2: Add `WorkerNode` Model**
   - **Details:** Create the `WorkerNode` SQLAlchemy model in `cloud-saas/app/models.py`.
     - Fields: `worker_id` (String, PK), `secret_hash` (String), `labels` (JSON), `version` (String), `git_commit` (String), `last_heartbeat` (DateTime), `status` (String).
   - **Dependencies:** None

3. [x] **Task 1.3: Create `Assignment` and `Lease` Models**
   - **Details:** 
     - Create `Assignment` (id, scraper_account_id, visa_center, date_range, polling_interval, priority, status).
     - Create `Lease` (id, assignment_id, worker_id, expires_at, created_at).
   - **Dependencies:** Task 1.2

4. [x] **Task 1.4: Refactor `ScraperAccount` Model**
   - **Details:** Remove deprecated WAF fields (e.g. `is_active`, `consecutive_failures`). Add `preferred_worker_id` (FK to WorkerNode.worker_id) and `status` ("Idle", "Leased", "Banned").
   - **Dependencies:** Task 1.2

5. [x] **Task 1.5: Create `EventLog` Model**
   - **Details:** Generic JSON log. Fields: `id`, `source`, `worker_id`, `assignment_id`, `severity`, `event_type` (String), `payload` (JSON), `created_at`.
   - **Dependencies:** Task 1.2, 1.3

6. [x] **Task 1.6: Database Migrations**
   - **Details:** Generate and apply Alembic migrations (or update `init_db.py`) to reflect all the new models safely in the Postgres DB.
   - **Dependencies:** Task 1.3, 1.4, 1.5

---
## Execution Notes
- **Outcome**: Successfully separated all local automated WAF scraping elements out of `cloud-saas` (moved to `operator-agent/core`).
- **Database**: 
  - `WorkerNode`, `Assignment`, `Lease`, and generic JSON `EventLog` schemas fully modeled in SQLAlchemy.
  - Added legacy column fallback (`ALTER TABLE scraper_accounts ADD COLUMN preferred_worker_id`) to `init_db.py` to prevent data loss.
- **Next step**: SaaS is successfully stripped down and prepared to act exclusively as an Orchestrator.
