# Scraper Automation Workflow & Gap Analysis

This report outlines the workflow for the Scraper (Monitoring) Execution Plane from the perspective of the end-user (Travel Agent), along with architectural gaps and pending items required to fully automate and optimize the scraping process.

---

## 1. The End-User (Travel Agent) Workflow

From the travel agent's perspective, the scraping mechanism should be largely invisible but highly transparent. They do not manage the technical workers, but they need to know the system is actively working on their behalf.

### Phase A: Configuration (Proactive)
1. **Resource Provisioning:** The travel agent (or SaaS Admin) uploads their pool of `PortalAccount`s (e.g., GVC login credentials) and `Proxy` IPs into the SaaS dashboard.
2. **Assignment Creation (Watchlist):** The agent defines what the scrapers should look for by creating an `Assignment`. 
   - *Example:* "Monitor GVC Lahore (VAC 138) for dates between Oct 1 and Oct 15."
3. **Status Dashboard:** The agent views a "Scraper Health" dashboard. This provides peace of mind by showing real-time metrics:
   - *Active Watchlists:* Which VACs are currently being monitored.
   - *Last Checked:* e.g., "Lahore was last checked 12 seconds ago."
   - *Resource Health:* e.g., "4/5 Accounts Healthy, 1 Proxy in Cooldown."

### Phase B: Execution (Automated Background)
4. **Lease Distribution:** The SaaS **Scheduler** assigns `Leases` to headless Scraper containers running on the VPS. 
5. **Continuous Polling:** 
   - The Scraper worker logs in using CapSolver (which is already proven and working).
   - It rotates through the required API endpoints to check calendar availability.
6. **Event Emitting:** 
   - If a WAF block occurs, the Scraper emits a `RATE_LIMIT` event, and the SaaS dynamically puts that specific Proxy or Account into a cooldown state.
   - If a slot opens, the Scraper emits a `SLOT_FOUND` event, which immediately triggers the Booker pipeline (as detailed in `01-booking-automation-workflow.md`).

---

## 2. Scraper Worker Architecture (Current State)
- **Headless Execution:** Scrapers run as separate Docker containers on the VPS. They poll the SaaS for instructions, execute them using `curl_cffi` (for TLS masking) and CapSolver, and return JSON events.
- **Statelessness:** Scrapers do not make booking decisions. They solely report what they see on the calendar.

---

## 3. Gaps & Pending Items in Scraper Automation

To make the scraping engine robust and cost-effective, the following gaps need to be addressed:

### Gap 1: Global vs. Tenant-Isolated Scraping (Critical Architectural Decision)
* **The Issue:** If Tenant A and Tenant B both want to monitor GVC Lahore, should the system spawn two separate scrapers (using two different accounts/proxies), or one global scraper?
* **The Solution:** Scraping should be **Globalized**. The SaaS backend should aggregate all tenant requests into a unified list of `Assignments`. If 50 agents want Lahore, only one global Scraper checks Lahore. When a slot is found, the Scheduler routes the bookings to the respective tenants based on their queue priority. This prevents burning through proxies unnecessarily and avoids DDoSing the visa portal.
* **Pending Task:** Update the SaaS Scheduler to deduplicate tenant watchlists into unified global `Assignments`.

### Gap 2: Adaptive Polling & WAF Evasion
* **The Issue:** A static polling interval (e.g., exactly every 5 minutes) is a massive red flag for WAFs like Imperva and Cloudflare.
* **The Solution:** Implement **Jitter** and **Adaptive Polling**. 
   - Scrapers must introduce random sleep intervals (jitter) between requests.
   - If a Scraper detects increased WAF friction (e.g., forced captchas on every page), it should signal the SaaS to temporarily slow down the `polling_interval` for that specific provider.
* **Pending Task:** Enhance the worker's `slot_monitor.py` to support randomized request pacing and adaptive back-off.

### Gap 3: Transparency UI (The "Trust" Gap)
* **The Issue:** Travel agents will abandon the platform if they feel it isn't "doing anything" while they wait for slots.
* **The Solution:** The SaaS UI must have a "Live Feed" component for Scrapers.
* **Pending Task:** Build a WebSocket or Polling-based UI component in the dashboard that streams harmless telemetry events from the scrapers (e.g., "Account 12 checking Lahore... No slots found").

### Gap 4: Defensive Account Rotation
* **The Issue:** GVC will ban accounts that check the calendar too many times in a 24-hour period, even if the proxy is clean.
* **The Solution:** The `ScoringPolicy` in the SaaS must track "Checks per Account per Day". Once an account hits a safe threshold (e.g., 200 checks), the Scheduler forces it into a "Rest" state and leases a fresh `PortalAccount` to the Scraper.
* **Pending Task:** Implement daily limit counters on the `PortalAccount` model and enforce them in the Scheduler's leasing logic.
