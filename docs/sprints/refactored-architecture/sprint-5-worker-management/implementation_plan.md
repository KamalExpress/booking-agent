# Sprint Plan: Worker Management & Proxy Abstractions

Based on your comprehensive architectural vision, this plan will implement the foundations for a distributed browser automation platform. Instead of haphazardly bolting on proxy logic, we will build out the core control-plane components you described.

We will break this down into a focused Sprint that accomplishes the most critical next steps.

## Open Questions

> [!WARNING]
> **Proxy Pool Assignment**
> Your document notes "Assignments reference a Proxy Pool instead of individual proxies." Currently, proxies are tied to the `ScraperAccount`. I will add a `proxy_pool_id` to the `Assignment` table and remove the static `proxy_string` from the `ScraperAccount`. Does this align with your vision?

> [!WARNING]
> **Worker IP Tracking**
> I will capture the worker's public IP address from the incoming `FastAPI` request headers during Registration and Heartbeats. Is this acceptable, or do you expect the worker to resolve its own IP (e.g. via `icanhazip.com`) and send it in the payload?

## Proposed Changes

---

### 1. Database Schema Extensions (SaaS)

We will introduce new models to support Worker Management and Proxy Abstractions.

#### [MODIFY] [models.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/models.py)
- **WorkerNode**: Add `ip_address` and `location` columns. Expand `labels` JSONB usage to include OS, CPU, RAM metrics captured during registration.
- **Assignment**: Add `proxy_pool_id` foreign key.
- **ScraperAccount**: Deprecate/Remove the static `proxy_string` field.
- **[NEW] ProxyProvider**: 
  - Columns: `id`, `name`, `type` (e.g., Residential, Datacenter), `host_port`, `credentials` (Encrypted JSON), `rotation_url`.
- **[NEW] ProxyPool**:
  - Columns: `id`, `name` (e.g., "Pakistan Residential"), `provider_id` (ForeignKey), `country`, `is_active`.

#### [MODIFY] [init_db.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/init_db.py)
- Add SQLAlchemy migration scripts to create the new tables and alter existing ones.

---

### 2. Worker Control Plane API

Enhance the worker communication API to support state management and proxy provisioning.

#### [MODIFY] [worker.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/routers/worker.py)
- Update `/api/v1/worker/register` to save OS, CPU, RAM, and `ip_address` (from `request.client.host`).
- Update `/api/v1/worker/assignments/next` to return the `proxy_pool` name/id alongside the assignment.
- **[NEW]** `GET /api/v1/worker/proxy/{pool_name}`: Returns decrypted proxy credentials, host:port, and rotation URL for the requested pool.

---

### 3. Management UI (Dashboard)

Build out the first-class SaaS interfaces.

#### [MODIFY] [base.html](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/templates/base.html)
- Add "Workers" and "Proxy Pools" to the main sidebar navigation.

#### [MODIFY] [ui.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/routers/ui.py)
- **[NEW]** `GET /workers`: List all workers, their current status, IP, and location.
- **[NEW]** `GET /workers/{worker_id}`: Dedicated worker detail page showing capabilities, stats, and a log tail.
- **[NEW]** `POST /workers/{worker_id}/status`: Action endpoints to Disable, Ban, Drain, or Delete a worker.
- **[NEW]** `GET /proxies`: Management page to configure Proxy Providers and Proxy Pools.

#### [NEW] [workers.html](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/templates/workers.html) & [worker_detail.html](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/templates/worker_detail.html)
- UI templates matching the dark theme for managing worker fleets.

#### [NEW] [proxies.html](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/templates/proxies.html)
- UI templates for CRUD operations on Proxy Providers and Pools.

---

### 4. Worker Node Updates

Update the worker client to request proxies dynamically per-assignment rather than relying on the scraper account string.

#### [MODIFY] [api_client.py](file:///d:/AI/bookingbot/bookingagent/ttttt/operator-agent/api_client.py)
- **[NEW]** `get_proxy(pool_name)` method that calls the SaaS proxy endpoint.

#### [MODIFY] [slot_monitor.py](file:///d:/AI/bookingbot/bookingagent/ttttt/operator-agent/slot_monitor.py)
- During the assignment boot sequence, check if a `proxy_pool` is assigned.
- If assigned, call `get_proxy()` to fetch credentials and mount them into the Playwright browser context or `httpx` client.

## Verification Plan
1. **Migrations**: Verify the database schema updates cleanly.
2. **UI Review**: Inspect the new `/workers` and `/proxies` pages.
3. **End-to-End Simulation**: Create a mock proxy pool, attach it to an assignment, and verify the worker's HTTP logs indicate it successfully requested and mounted the proxy credentials from the SaaS.
