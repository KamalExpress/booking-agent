# SaaS Admin (Super Admin) Workflow & Gap Analysis

This report outlines the platform workflow from the perspective of the **SaaS Admin** (Super Admin). This role is responsible for the global infrastructure, worker node scaling, WAF evasion telemetry, and cross-tenant orchestration.

---

## 1. The SaaS Admin Workflow

### Phase A: Infrastructure & Tenant Management
1. **Tenant Onboarding:** The SaaS Admin creates new Tenant accounts, issues licenses, and sets global concurrency limits per Tenant.
2. **Global Scraping Configuration:** Using the `MonitorConfig` table, the Admin defines global scraping rules. They can instantly pause all scraping for a specific provider (e.g., if GVC undergoes major maintenance) or define global holidays.
3. **Worker Node Fleet Management:** The Admin spins up new VPS instances or Docker containers and registers their `secret_hash` to the `worker_nodes` table.

### Phase B: System Telemetry & Incident Response
4. **WAF Intelligence Monitoring:** The Admin watches the global `EventLog` and `WorkerLog` (network intercepts) to identify if a provider like Imperva has updated its TLS fingerprinting rules, causing a sudden spike in `RATE_LIMIT` or `CAPTCHA_FAILED` events across the worker fleet.
5. **Scheduler Auditing:** If a Tenant complains that their bookings aren't firing, the Admin uses the `SchedulerDecision` audit logs to trace exactly why a Booker worker bypassed that Tenant's queue (e.g., "Tenant ran out of healthy proxies").

---

## 2. Gaps & Pending Items for SaaS Admins

To maintain a highly available and scalable distributed system, the SaaS Admin requires advanced diagnostic and orchestration tools that are currently missing or incomplete:

### Gap 1: Worker Node Auto-Scaling Intelligence
* **The Issue:** Booker workers must be highly parallel to handle sudden mass slot drops. How does the SaaS Admin know when to spin up more Booker containers? 
* **The Solution:** The SaaS needs a "Queue Depth vs. Worker Availability" metric. If there are 50 pending `BookingTask`s but only 10 idle Booker workers available, the SaaS Admin dashboard should flash a warning to deploy more containers.
* **Pending Task:** Implement a real-time Worker Capacity dial in the SaaS Admin UI that calculates `(Idle Workers + Accepting Jobs) / Pending Tasks`.

### Gap 2: Global Assignment Deduplication & Routing
* **The Issue:** As discussed in the Scraper Workflow, scraping must be globalized to save resources. The SaaS Admin needs visibility into this deduplication engine.
* **The Solution:** The Admin needs an "Active Global Assignments" view showing exactly which worker is currently scraping which Visa Center on behalf of which aggregated Tenants.
* **Pending Task:** Build the SaaS Admin UI component to visualize the consolidated `Assignments` table and the live mapping of workers currently executing them.

### Gap 3: Centralized Captcha / API Key Management
* **The Issue:** The workers rely on third-party APIs (CapSolver, NopeCha) which cost money. If these API keys are managed by individual Tenants or hardcoded in worker `.env` files, updating them is a deployment nightmare.
* **The Solution:** API keys for global evasion services (like CapSolver) should be managed centrally in the `SystemSetting` table (encrypted). The SaaS securely injects these keys into the `Lease` payload sent to the Worker Node.
* **Pending Task:** Migrate CapSolver API keys into the encrypted `SystemSetting` table and update the Worker API Client to accept these keys dynamically upon lease generation.
