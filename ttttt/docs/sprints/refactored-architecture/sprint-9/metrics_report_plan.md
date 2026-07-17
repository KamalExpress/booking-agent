# Feasibility Report & Plan: Advanced Billing Metrics

> [!NOTE]
> **Status: Deferred to Backlog.** 
> As discussed, we are keeping the headless workers "thin" and relying on the Decodo/CapSolver native dashboards for metrics right now. In the future, implementing an Event Sourcing mechanism will make aggregating these metrics much cleaner.

You asked if we can track **Captcha Success/Failure rates** and **Proxy IP Bandwidth (KBs/MBs/GBs)** using the logs and database schemas we currently have set up.

## Current System Capabilities
Right now, the Cloud SaaS acts as a passive control plane while the Headless Workers execute the logic. 
- **Captchas:** The worker solves captchas natively via CapSolver/NopeCha and logs the results locally (e.g. `logging.info("CapSolver solved the CAPTCHA")`). However, it **does not** explicitly report these successes or failures back to the SaaS database via the API.
- **Proxy/IP Usage:** The `ScraperAccount` table stores the assigned `proxy_string`, so we know *which* IP is used for an assignment. However, the worker currently **does not** tally the byte sizes of the requests and responses it makes.

**Conclusion:** We cannot generate these stats *as-is*, but our architecture is perfectly positioned to handle this with a few lightweight upgrades.

---

## Proposed Implementation Plan

> [!IMPORTANT]
> To avoid cluttering the `EventLog` table with thousands of micro-transactions (e.g., logging every single 5KB request), we should implement **Metric Aggregation** in the worker, and have it report rolled-up stats to the SaaS every few minutes.

### Phase 1: SaaS Schema Upgrades (`models.py` & `worker.py`)
- **[NEW MODEL]** `WorkerMetric`: A new database table specifically designed for billing and quotas.
  - Columns: `id`, `tenant_id`, `worker_id`, `proxy_ip`, `captcha_solved_count`, `captcha_failed_count`, `bandwidth_bytes_used`, `created_at`.
- **[NEW ENDPOINT]** `POST /api/worker/metrics`: An endpoint for the workers to submit their aggregated telemetry.

### Phase 2: Worker Telemetry (`operator-agent/`)
- **Bandwidth Tracking (`curl_cffi` & Playwright):** 
  - Update the `SessionManager` in the worker to intercept and sum the `len(response.content)` for every request made.
  - Parse the proxy string to extract the raw IP being utilized.
- **Captcha Tracking (`browser_trust.py`):** 
  - Increment a local counter every time the `_solve_capsolver` function succeeds or times out.
- **Telemetry Loop:** 
  - Have the worker hold these metrics in memory and flush them to the SaaS `POST /api/worker/metrics` endpoint on a set interval (e.g., every 5 minutes or at the end of an assignment lease).

### Phase 3: SaaS Dashboard (UI)
- **[NEW PAGE]** `/billing` or `/metrics`: A visual dashboard for the SaaS Super Admin and Tenant Admins.
- Display graphs (using a lightweight library like Chart.js) or metric cards showing:
  - **Bandwidth Burn Rate** per Tenant / Proxy IP (automatically formatted from Bytes to MBs/GBs).
  - **Captcha Efficiency %** (Solved vs Failed).

---

## Open Questions for You

> [!TIP]
> 1. Do you want to implement this plan right now as part of our current sprint, or add it to the backlog for a future phase?
> 2. Should Tenant Admins be able to see their Bandwidth/Captcha usage, or is this strictly for your Super Admin cost-monitoring purposes?
