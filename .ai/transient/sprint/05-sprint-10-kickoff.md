# Sprint 10 Kickoff: Architecture Hardening

## Background
In the previous session, we stabilized the deployment pipeline by creating a `staging` branch (and its corresponding `feature/staging` remote) with a fully automated Portainer stack.
We implemented `entrypoint.sh` to handle automated database seeding, Alembic `stamp head` (for existing DBs), and `upgrade head`. We also successfully booted a headless `operator-agent` in the same Docker stack for end-to-end testing.

## Current Objective: Epic 5 (The Service Layer)
The Control Plane is currently a collection of bloated endpoints (especially `routers/worker.py` and `routers/assignment.py`). 
Our goal is to refactor the core execution model into a robust distributed orchestration platform.

### The Approved Architecture Plan:
1. **Service Layer Abstraction:**
   - Move business logic out of `routers/` and into `services/`.
   - **Target Services:** `WorkerService`, `LeaseService`, `MaintenanceService`, `EventService`.
2. **Durable Stateful Leases:**
   - Instead of deleting `Lease` records when assignments finish, we will keep them and update their `status` (e.g., `COMPLETED`, `FAILED`, `EXPIRED`).
   - This ensures a historical audit trail of worker execution.
3. **The MaintenanceService (No Global Threads):**
   - We must strictly avoid FastAPI `BackgroundTasks` running infinite while-loops.
   - We will implement a `MaintenanceService.run_cleanup_cycle()` that encapsulates:
     - `LeaseCleanup` (Expiring dead leases)
     - `WorkerCleanup` (Marking dead workers offline)
     - `NotificationCleanup` (Pruning old logs)
   - This cleanup cycle will be invoked defensively across multiple API endpoints (e.g., when a worker requests a job, or an assignment is created) to ensure the system self-heals statelessly.

## Next Steps for the Agent
1. Read `.ai/permanent/architecture/04-worker-management.md` and `sprint10.md` (if available in root) for deeper context.
2. Begin by drafting `app/services/lease_service.py` and `app/services/worker_service.py`.
3. Refactor the endpoints in `app/routers/worker.py` to delegate to these services.
4. DO NOT attempt to rewrite the entire application at once. Start with the Worker API endpoints and test them iteratively using the Staging stack.
