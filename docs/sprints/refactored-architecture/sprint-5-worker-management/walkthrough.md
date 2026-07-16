# Sprint 5: Worker Management & Lease Orchestration

## Overview
This sprint fundamentally reshapes how the SaaS communicates with remote worker nodes by implementing a decoupled, versioned Runtime Configuration system and a strict Lease abstraction for job assignments. Additionally, a new comprehensive Worker Management UI provides real-time oversight of the bot fleet.

## Key Changes

### 1. Architectural Refinements
- **Decoupled Runtime Config**: Removed runtime settings (timeouts, captchas) from individual assignment objects. Workers now independently fetch a cached, version-controlled global runtime configuration.
- **Strict Lease Lifecycle**: Workers no longer just grab an "Assignment". They are granted a time-bound `Lease` that encompasses an execution context. Leases have strict states (`Pending`, `Leased`, `Running`, `Completed`, `Expired`, `Cancelled`, `Failed`, `Abandoned`).
- **Worker Scheduling States**: Workers now have explicit scheduling states allowing operators to gracefully Drain or Maintenance them without deleting them.

### 2. SaaS API Endpoints (`worker.py`)
- **`/register`**: Expanded payload to collect deep hardware capabilities (CPU cores, RAM), OS (Windows/Linux), architecture (x86_64/ARM), Python, Chrome, and Playwright versions. Enforces minimum worker versions against the `WorkerVersion` table.
- **`/heartbeat`**: Now expects `runtime_config_version`, `local_ip`, and `public_ip`. Updates both the worker's status and the lifetime of any active Leases the worker holds. Returns a flag to trigger the worker to refresh its config if a new version is available.
- **`/runtime-config`**: New endpoint serving the versioned payload.
- **`/assignments/next`**: Refactored to issue `Lease` objects instead of raw assignments. Includes scoring logic that respects Scraper Account preferred workers.

### 3. Operator Interface (`ui.py` & Templates)
- **Fleet Dashboard (`/workers`)**: Added a table displaying all workers, their current connection state, hardware, and last heartbeat age.
- **Worker Detail View (`/workers/{worker_id}`)**:
  - Detailed hardware and network breakdown (detecting proxy mismatches).
  - Quick action controls (Accept Jobs, Stop Accepting, Drain, Disable, Maintenance).
  - Tabbed interface separating Live Operations (active leases) from Historical Data (event logs).

### 4. Worker Client Integration (`api_client.py` & `slot_monitor.py`)
- **Enhanced `SaaSClient`**: Now uses `psutil` and `platform` to gather accurate telemetry on startup.
- **Heartbeat & Telemetry**: Runs a daemon thread maintaining connectivity and syncing configuration versions.
- **Lease Processor**: Refactored `slot_monitor.py` to extract the execution context from the new lease structure, separating configuration acquisition from the polling loop.

## Verification
- Migrations successfully ran via `init_db.py`.
- Endpoints successfully parsing payload and HMAC logic updated.
- Worker gracefully handles leases and heartbeats.

> [!NOTE]
> Please restart your Docker containers (`docker-compose down && docker-compose up --build`) to apply the database migrations and serve the new UI templates!
