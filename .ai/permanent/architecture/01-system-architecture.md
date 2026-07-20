# System Architecture: The Control Plane / Execution Plane Split

## Purpose
To orchestrate distributed headless workers for visa appointment scraping and slot booking while shielding the central SaaS from WAF (Web Application Firewall) bans.

## Core Architecture Shifts (Sprint 10)
- **Central Scheduler Brain:** The SaaS backend evaluates worker capabilities (`supports_scraping`, `supports_booking`) and dynamically bundles `PortalAccounts`, `Proxies`, and `Tasks` into secure, versioned `Leases`. Workers are entirely stateless and make zero targeting decisions.
- **Dual Worker Pools:**
  - **Scrapers:** Polling entities that optimize for coverage, low detection, and continuous visa center monitoring.
  - **Bookers:** Reactive, event-driven entities that only act when a `BookingTask` is generated. They prioritize speed and minimize account burn.
- **Dynamic Bindings:** Proxies are no longer statically bound to accounts. The Scheduler dynamically pairs a healthy Proxy with a healthy Account at the moment of lease creation based on configurable `ScoringPolicies`.
- **Event-Driven Pipeline:** A `SLOT_FOUND` event from a Scraper automatically triggers the creation of unique, deduplicated `BookingTask` records, which are then routed to available Booker workers.

## Responsibilities
- **Cloud SaaS (Control Plane):** Manages the `SchedulerService`, calculates resource health scores, enforces dynamic cooldown policies, manages billing, tenants, UI dashboards, and push notifications. It **never** touches external portals.
- **Headless Workers (Execution Plane):** Distributed nodes that simply poll for `Leases`, execute the bundled payload (browser automation, captcha bypass), and return standardized success/failure events.

## Public Interfaces
- `POST /api/worker/login`
- `POST /api/worker/slots`
- `POST /api/worker/heartbeat`
- `POST /api/worker/log`

## Dependencies
- PostgreSQL (SaaS Storage)
- Web Push API (SaaS Notifications)
- CapSolver / NopeCha (Worker Captcha)
- Playwright / curl_cffi (Worker Orchestration)

## Invariants
- The SaaS must never initiate HTTP requests to the Visa portals.
- Proxies and Accounts must be dynamically coupled only during an active `Lease`.
- A `BookingTask` must have a DB-level unique constraint on `(visa_center, target_date, target_time, active_status)` to prevent race conditions during deduplication.
- Workers must pull assignments (polling), the SaaS does not push connections to the workers (allowing workers to sit behind NATs/Firewalls).

## Failure Modes & Auditing
- **Worker Disconnect:** If a worker dies, its `Lease` expires based on a strict TTL (`expires_at`, `heartbeat_at`). The Scheduler reclaims the resources instantly.
- **WAF Block / Portal Errors:** Workers return standard enums (`LOGIN_FAILED`, `CAPTCHA_FAILED`, `PROXY_TIMEOUT`). The SaaS translates these into independent cooldowns (e.g., cool down the proxy but keep the account active).
- **Scheduling Audit:** Every selection attempt is permanently recorded in `SchedulerDecision`, logging exactly why a specific account/proxy was chosen or why the queue failed to dispatch.

## Extension Points
- Can deploy workers on residential proxies, AWS workspaces, or Raspberry Pis seamlessly because the API is standard HTTP polling.
- The `Provider` dimension enables scaling out from a single visa portal (e.g., VFS) to multiple portals (BLS, GVC) gracefully.

## Deployment Topology
- **Strictly VPS & Docker:** The system runs exclusively on a cloud VPS managed via Portainer. Agents must NEVER attempt to run Docker containers or Alembic database migrations locally.
- **Environment Split:**
  - `feature/staging` branch deployed as the **Staging Stack** (contains all new booking/waitlist features).
  - `feature/headless-worker` branch deployed as the **Production Stack** (currently stable and in use).

## Related Source Directories
- `ttttt/cloud-saas/app/services/scheduler_service.py`
- `ttttt/cloud-saas/app/services/scoring_policy.py`
- `ttttt/operator-agent/main.py`

---
*Last Reviewed: Sprint 10 | Implementation Verified: PENDING | Owner: Knowledge Manager | Confidence: High*
