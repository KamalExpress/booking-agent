# Sprint Plan: Worker Management & Lease Orchestration

Based on your final architectural feedback, we have separated the Runtime Config from the Lease lifecycle, normalized worker capabilities, and established formal states for leases and scheduling. This creates a highly scalable foundation for a distributed browser automation platform.

## Proposed Changes

---

### 1. Database Schema Refinements (SaaS)

We will introduce new models and fields to support richer worker states, scheduling policies, and capability querying.

#### [MODIFY] [models.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/models.py)
- **WorkerNode**:
  - **Network**: Add `observed_ip`, `public_ip`, `local_ip`.
  - **Normalized Capabilities**: Add `os`, `architecture`, `chrome_version`, `playwright_version`, `python_version`, `cpu_cores`, `ram`, `max_concurrency`, `current_concurrency`.
  - **Labels**: Formalize Kubernetes-style labels in `labels` JSONB (e.g., `system.os=windows`, `network.residential=true`).
  - **State**: Add `scheduling_state` (Accepting Jobs, Stop Accepting Jobs, Draining, Disabled) alongside standard worker status (Online/Offline/Error).
- **Assignment**:
  - Add `routing_policy_id` (ForeignKey) for future Kubernetes-style label scheduling requirements.
- **ScraperAccount**:
  - Keep `proxy_string` (mark as legacy fallback). Add `proxy_mode` enum (`LEGACY`, `POOL`).
- **Lease**:
  - Expand to track `status` (`Pending`, `Leased`, `Running`, `Completed`, `Expired`, `Cancelled`, `Failed`, `Abandoned`).
  - Add `last_heartbeat` to the Lease itself (updated when worker heartbeats).
- **[NEW] WorkerVersion**:
  - Track minimum supported versions. SaaS refuses registration/heartbeats for deprecated versions.

#### [MODIFY] [init_db.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/init_db.py)
- Add SQLAlchemy migrations to create/update tables safely without dropping data.

---

### 2. Unified Worker Control Plane API

We will implement the decoupled Runtime Config and Lease architecture.

#### [MODIFY] [worker.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/routers/worker.py)
- **Registration (`/register`)**: Expand payload to ingest all new normalized capability fields and labels. Reject if version is below minimum supported.
- **Runtime Config (`/runtime-config`)**:
  - Versioned response (`version`, `ttl`, `captcha`, `proxy`, `browser`, `polling`, `feature_flags`, `limits`).
- **Heartbeat (`/heartbeat`)**:
  - Capture `public_ip`, `local_ip`, and `runtime_config_version`.
  - SaaS replies with `refresh_runtime_config=true` if versions mismatch.
  - Updates `last_heartbeat` on both the Worker and its active `Lease`.
- **Lease Provisioning (`/assignments/next`)**:
  - Returns a pure execution context (Lease ID, Assignment context, Scraper Account credentials, expiry, heartbeat_interval).

---

### 3. Management UI (Dashboard)

Build out the first-class SaaS interfaces prioritizing worker observability.

#### [MODIFY] [base.html](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/templates/base.html) & [ui.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/routers/ui.py)
- Add "Workers" to the main sidebar navigation.
- **[NEW]** `GET /workers`: Inventory view displaying Worker Status, Country, IPs, Current Job, Stats, and Last Seen.
- **[NEW]** `GET /workers/{worker_id}`: Dedicated detail page with **Live** and **Historical** tabs showing deep health metrics, Kubernetes-style labels, recent events, and statistics.
- **[NEW]** Action Buttons: Accept Jobs, Stop Accepting Jobs, Drain, Disable, and Maintenance.

#### [NEW] [workers.html](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/templates/workers.html) & [worker_detail.html](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/templates/worker_detail.html)
- UI templates matching the dark theme for managing worker fleets.

---

### 4. Worker Client Modernization

The worker must adapt to the decoupled config/lease lifecycle.

#### [MODIFY] [api_client.py](file:///d:/AI/bookingbot/bookingagent/ttttt/operator-agent/api_client.py)
- Update `register_worker()` to transmit comprehensive hardware/software capabilities.
- Update `send_heartbeat()` to send `runtime_config_version`. Handle `refresh_runtime_config` flag in response.
- Update `get_runtime_config()` to cache config in memory with TTL.

#### [MODIFY] [slot_monitor.py](file:///d:/AI/bookingbot/bookingagent/ttttt/operator-agent/slot_monitor.py)
- Refactor loop: Heartbeat -> Check Runtime Config -> Get Lease -> Execute -> Heartbeat.
- Respect Scheduling State (Accepting Jobs vs Stop Accepting).

## Verification Plan
1. **Migrations**: Verify SQLite schema updates correctly.
2. **Telemetry Validation**: Boot a worker, verify the SaaS captures full capabilities, IP mismatch (if any), and enforces minimum version.
3. **Lease & Config Flow**: Verify worker caches Runtime Config, only refreshing when SaaS bumps the version during heartbeat. Verify worker executes Assignment based purely on Lease payload.
