# Kamal Express SaaS - Project Context

This document serves as a persistent context reference for AI agents working on the Kamal Express platform to avoid re-reading extensive logs and files.

## Project Overview

Kamal Express is a **distributed browser automation platform**, currently tailored for scraping and booking on visa portals. To bypass aggressive anti-bot protections (like Imperva, Cloudflare, DataDome) that flag traditional cloud IPs (e.g., Hetzner, AWS), the architecture is split into two distinct planes:

### 1. Cloud SaaS (Control Plane)
- **Location:** `ttttt/cloud-saas/`
- **Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, Jinja2 (server-side templates), Docker.
- **Responsibilities:** 
  - Orchestrating tasks and issuing leases via a generic Worker API (`/api/worker/...`).
  - User and Tenant management (Super Admins vs Tenant Admins).
  - Monitoring worker health, statistics, and assignment statuses.
  - Distributing notifications (Web Push, Telegram, WhatsApp, Email, SMS).
  - Securely managing secrets (e.g., CAPTCHA API keys via Fernet encryption).
- **Note:** The SaaS *never* touches the visa portal directly.

### 2. Operator Agent (Execution Plane / Worker Node)
- **Location:** `ttttt/operator-agent/` (and GUI variants)
- **Tech Stack:** Python, Playwright.
- **Responsibilities:**
  - Running on diverse environments (Windows Desktop, Mini PCs, residential IPs).
  - Authenticating and maintaining trusted sessions/cookies.
  - Solving CAPTCHAs and handling human-in-the-loop interventions.
  - Requesting jobs from the SaaS (`get_jobs`) and reporting results (`report_slot`).

## Current Architecture & Design Decisions

- **Worker Abstraction:** The system treats scraper instances as generic "Workers". Workers advertise capabilities (e.g., Residential IP, Chrome, Pakistan Location) and the SaaS schedules assignments accordingly.
- **Proxy Pools:** Instead of sending raw proxy IPs directly, the SaaS utilizes "Proxy Pools" and "Proxy Providers", allowing proxy routing to be dynamically matched based on the worker's capabilities.
- **Worker States:** Workers use comprehensive statuses (`Online`, `Offline`, `Disabled`, `Draining`, `Maintenance`, `Blocked`, `Error`) rather than simple binary states. "Draining" is particularly important for allowing a worker to finish an assignment without taking new ones during updates.
- **Deployment Strategy:** The Cloud SaaS is deployed to a Hetzner VPS via Portainer Stacks. A deployment script (`vps-setup/deploy.sh`) is provided because Portainer's UI doesn't force a `--build` on locally built images when syncing from Git.

## Common Operations & Gotchas

- **Adding New Features to SaaS:** The frontend is built using server-side rendered HTML (`app/templates/`) and TailwindCSS (via generic classes in `.css` or utility classes). 
- **Git Ignore Gotcha:** The directory `ttttt` was previously accidentally ignored by `*.env` typo in the root `.gitignore`. This has been fixed to `*.env`. Always ensure new files (like new `.html` templates) are tracked by git so Portainer pulls them.
- **Docker Compose Topology:** The standard `docker-compose.yml` in the root is a barebones definition containing only the SaaS Control Plane. 
  - **Production:** The true production stack is `vps-setup/docker-compose.prod.yml`. It spins up all three containers (`cloud-saas`, `db`, and `operator-worker`) on a single network for local execution.
  - **Staging:** The staging stack is `docker-compose-staging.yml`. Like production, it spins up all three containers (`postgres_staging`, `cloud-saas-staging`, `operator-agent-staging`).
  - **Worker Config:** The headless worker expects `SAAS_BASE_URL` to connect to the Control Plane. Do NOT use `BASE_URL` in the compose files for the worker, as `headless.py` specifically reads `SAAS_BASE_URL`.

## Next Development Priorities (Sprint Guidance)
1. **Device Fingerprinting & Real IP extraction:** Update `ProxyHeadersMiddleware` in FastAPI to bypass Portainer/Docker reverse proxy IPs and log real user location via GeoIP.
2. **Dynamic Appointment Types:** Make Visa Appointment Types (0, 2, 6, 26) dynamically selectable on the Assignments Creation interface.
3. **Stale Notification Cleanup:** Prune inactive Web Push subcriptions from the DB.
4. **Workers Management UI:** Deepen the UI for worker health, actions (disable, drain), statistics, and logs.
5. **Scheduler Improvements:** Assign leases based on capabilities.
6. **Secrets Manager:** Expand the current CAPTCHA key manager to handle general secrets.
7. **Proxy Provider & Proxy Pool Abstraction.**
