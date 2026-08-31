# Runtime Incidents & Fixes Discovered (Live Runtime Register)

## 1. Overview & Purpose
This document registers all **Runtime Incidents & Fixes Discovered** during live production operations and high-traffic slot release windows.

Each incident captures:
- **Incident ID & Severity**
- **Observed Runtime Symptom** (Exact log trace / HTTP status)
- **Root Cause Analysis**
- **Immediate Hotfix Applied** (Commit SHA & Code Diff)
- **Remediation & Architectural Safeguard**

---

## 2. Domain A: Cloud SaaS & Control Plane Runtime Incidents

### INC-20260828-01: Web Push Notifications Blocked by `UnboundLocalError: Lease`
- **Severity:** `SEV-1 (Critical Outage)`
- **Discovered At:** August 28, 2026 — 22:30 PKT (During active slot opening)
- **Observed Runtime Symptom:**
  Workers detected open slots and posted `SLOT_FOUND` to `/api/v1/worker/logs`. The SaaS backend returned **HTTP 500 Internal Server Error**:
  ```text
  UnboundLocalError: local variable 'Lease' referenced before assignment
  ```
  Admins and agency staff received zero Web Push notifications; live dashboard events failed to broadcast.
- **Root Cause:**
  Python bytecode compiler scoping rule. A nested import statement `from models import ... Lease` inside `elif req.event_type == "SLOT_FOUND":` at line 375 caused the Python compiler to treat `Lease` as a function-scoped local variable throughout the entire `submit_logs()` function. When execution reached line 295 (`db.query(Lease)`), line 375 had not yet executed, triggering the `UnboundLocalError`.
- **Fix Discovered & Applied:**
  Promoted all model imports (`Lease`, `SlotAvailability`, `BookingTask`, etc.) to top-level module imports, initialized `lease = None` at function entry, and eliminated the nested import.
- **Commit:** [`6de7ff8`](https://github.com/KamalExpress/booking-agent/commit/6de7ff8) / [`b763efb`](https://github.com/KamalExpress/booking-agent/commit/b763efb) on `feature/prod-july2026`.
- **Outcome:** Notifications immediately resumed delivering reliably across client devices.

---

### INC-20260828-02: Worker Lease Recovery HTTP 500 on `AttributeError: dict object`
- **Severity:** `SEV-2 (High Impact)`
- **Discovered At:** August 28, 2026 — 22:42 PKT
- **Observed Runtime Symptom:**
  When a worker reconnected and called `GET /api/v1/worker/assignments/next`, the server returned HTTP 500:
  ```text
  AttributeError: 'dict' object has no attribute 'portal_account_id'
  ```
- **Root Cause:**
  `lease_service.get_existing_lease_for_worker()` returned a serialized dictionary representation of the lease, but `worker.py:get_next_assignment()` expected the SQLAlchemy `Lease` model instance to query relationships.
- **Fix Discovered & Applied:**
  Updated `get_existing_lease_for_worker()` to return the SQLAlchemy `Lease` model instance directly.
- **Commit:** [`810529d`](https://github.com/KamalExpress/booking-agent/commit/810529d).

---

### INC-20260828-03: Scheduler Crash on Legacy `auto_dispatch_queue` Arguments
- **Severity:** `SEV-2 (High Impact)`
- **Discovered At:** August 28, 2026 — 22:45 PKT
- **Observed Runtime Symptom:**
  Logging endpoint crashed inside `scheduler.handle_event` with:
  ```text
  TypeError: auto_dispatch_queue missing 2 required positional arguments
  ```
- **Root Cause:**
  `auto_dispatch_queue` had been updated to accept rich slot payloads `(visa_center, slots, assignment_id, target_date)`, but a legacy caller in `handle_event` still passed only `(visa_center, slot_count)`.
- **Fix Discovered & Applied:**
  Added default parameters (`slots=None, assignment_id=None, target_date=None`) and removed the duplicate legacy call in `handle_event`.
- **Commit:** [`2ea89be`](https://github.com/KamalExpress/booking-agent/commit/2ea89be).

---

### INC-20260828-04: Resource Pool Starvation via Orphaned Leased Accounts & Proxies
- **Severity:** `SEV-2 (High Impact)`
- **Discovered At:** August 28, 2026 — 23:10 PKT
- **Observed Runtime Symptom:**
  Portal accounts and proxies remained locked in `LEASED` status indefinitely after worker containers were restarted or dropped connections, eventually exhausting available pool resources.
- **Root Cause:**
  If a worker node terminated abruptly without triggering an unlease hook, the database record remained `LEASED` until manually reset.
- **Fix Discovered & Applied:**
  Implemented `_reconcile_orphan_resources()` in `maintenance_service.py` within the periodic background cleanup cycle to auto-reconcile resources whose leases have expired.
- **Commit:** [`f42b943`](https://github.com/KamalExpress/booking-agent/commit/f42b943).

---

### INC-20260829-05: Scheduler HTTP 500 on `TypeError: score_proxy` Signature Mismatch
- **Severity:** `SEV-1 (Critical Outage)`
- **Discovered At:** August 29, 2026 — 01:44 PKT
- **Observed Runtime Symptom:**
  Production SaaS threw HTTP 500 on `/api/v1/worker/assignments/next`:
  ```text
  TypeError: ScoringPolicy.score_proxy() takes 1 positional argument but 2 were given
  ```
- **Root Cause:**
  `scheduler_service.py` was updated to pass `due_assignment.provider` to `score_proxy`, but `scoring_policy.py` on production expected only `(proxy)`.
- **Fix Discovered & Applied:**
  Updated `score_proxy` and `score_account` signatures to accept optional `task_provider: str = "GVC"`, `*args`, and `**kwargs`.
- **Commit:** [`730a610`](https://github.com/KamalExpress/booking-agent/commit/730a610).

---

### INC-20260829-06: Production Server Crash on Missing `provider_health` Column
- **Severity:** `SEV-1 (Critical Outage)`
- **Discovered At:** August 29, 2026 — 01:50 PKT
- **Observed Runtime Symptom:**
  Production SaaS threw HTTP 500 during lease scheduling:
  ```text
  AttributeError: 'PortalAccount' object has no attribute 'provider_health'
  ```
- **Root Cause:**
  Multi-provider health tracking added on staging queried `account.provider_health`, but the production database had not run that Alembic migration. Direct property access threw `AttributeError`.
- **Fix Discovered & Applied:**
  Guarded lookups using `getattr(account, 'provider_health', None)` and `getattr(account, 'health_score', 100)`.
- **Commit:** [`b072184`](https://github.com/KamalExpress/booking-agent/commit/b072184).

---

## 3. Domain B: Execution Plane (Workers & WAF) Runtime Incidents

### INC-20260829-01: Imperva Bot Rule B10 Detection via Document Navigation Header Anomaly
- **Severity:** `SEV-1 (Critical Outage)`
- **Discovered At:** August 29, 2026 — 00:20 PKT
- **Observed Runtime Symptom:**
  Workers attempting to log in were blocked by Imperva with HTTP 200 containing a 212-byte JavaScript challenge (`/_Incapsula_Resource?...`). Header `x-iinfo: ... B10(...)` was returned and sessions were tainted.
- **Root Cause:**
  The worker sent `Origin: https://...` and `Accept: application/json` on top-level GET document navigations. Real Chrome desktop browsers never send `Origin` on document GET navigations. Imperva flagged this anomaly as Bot Rule B10.
- **Fix Discovered & Applied:**
  Aligned headers with genuine browser signatures: stripped `Origin` on GET, configured `Accept: text/html...`, `Sec-Fetch-Site: none`, `Sec-Fetch-User: ?1`, and `Upgrade-Insecure-Requests: 1`.
- **Commit:** [`17db917`](https://github.com/KamalExpress/booking-agent/commit/17db917).

---

### INC-20260829-02: Operator Worker Container Crash on Unrecognized Schema Field
- **Severity:** `SEV-1 (Critical Outage)`
- **Discovered At:** August 29, 2026 — 00:34 PKT
- **Observed Runtime Symptom:**
  Production operator container crashed on startup with:
  ```text
  TypeError: unexpected keyword argument 'supported_providers'
  ```
- **Root Cause:**
  The worker registration API client sent `supported_providers`, which the SaaS backend registration endpoint did not accept in its schema.
- **Fix Discovered & Applied:**
  Removed `supported_providers` from registration payload and added `**kwargs` resilience in `api_client.py`.
- **Commit:** [`563cac2`](https://github.com/KamalExpress/booking-agent/commit/563cac2).
### INC-20260831-01: Alembic Revision Lookup Failure on Staging Branch Downgrade
- **Severity:** `SEV-1 (Critical Outage)`
- **Discovered At:** August 31, 2026 — 16:08 PKT
- **Observed Runtime Symptom:**
  Deploying `feature/staging-july2026` caused the Staging `cloud-saas` container to enter an infinite restart crash loop with error:
  ```text
  ERROR [alembic.util.messaging] Can't locate revision identified by '015_booking_confirmation_fields'
  FAILED: Can't locate revision identified by '015_booking_confirmation_fields'
  ```
- **Root Cause:**
  The persistent Staging PostgreSQL database volume had previously executed migrations up to `015_booking_confirmation_fields` during August development. When Staging was checked out to `feature/staging-july2026` (branched from July 28 baseline `eaad857`), the local `alembic/versions/` directory only contained revisions up to `012`. When `alembic upgrade head` executed on container startup, it queried `alembic_version` in the database, found `'015_booking_confirmation_fields'`, but could not locate the corresponding revision file on disk.
- **Fix Discovered & Applied:**
  1. Backported the 3 missing revision files (`014_portal_account_phone.py`, `015_booking_confirmation_fields.py`, and `e093ad7b8be7_execution_plane_abstraction.py`) into `app/alembic/versions/` on `feature/staging-july2026`.
  2. Enhanced `ttttt/cloud-saas/entrypoint.sh` with a self-healing fallback that detects migration lookup failures and automatically runs `python -m alembic stamp head` instead of crashing.
- **Commit:** [`cbbec8f`](https://github.com/KamalExpress/booking-agent/commit/cbbec8f) on `feature/staging-july2026`.
- **Status:** **Resolved**.

---

### INC-20260829-03: Imperva Dynamic JS Challenge (`_Incapsula_Resource`) Interception
- **Severity:** `SEV-1 (Critical Outage)`
- **Discovered At:** August 29, 2026 — 00:38 PKT
- **Observed Runtime Symptom:**
  During high traffic, Imperva served dynamic obfuscated JavaScript challenges (`_Incapsula_Resource`) during login and slot searches. `curl_cffi` was unable to execute JavaScript, failing authentication.
- **Root Cause:**
  Elevated Imperva threat level during quarterly slot opening required genuine browser JavaScript execution and client-side proof-of-work.
- **Fix Discovered & Applied:**
  Configured headless Playwright with stealth plugins to route over the worker's assigned Decodo proxy, execute the JS challenge, extract the resulting `incap_ses_*` and `visid_incap_*` cookies, and inject them into `curl_cffi`.
- **Commit:** [`9e9607d`](https://github.com/KamalExpress/booking-agent/commit/9e9607d) & [`befa310`](https://github.com/KamalExpress/booking-agent/commit/befa310).

---

### INC-20260829-04: Account Rate-Limiting & Proxy Block via Rapid Consecutive 403 Hammering
- **Severity:** `SEV-1 (Critical Outage)`
- **Discovered At:** August 29, 2026 — 01:35 PKT
- **Observed Runtime Symptom:**
  After logging in, workers received HTTP 403 Forbidden on `PUT /api/v1/periodslot/slots` and repeatedly hammered the endpoint every 3 seconds across all centers and dates, causing proxy reputation burn and portal bans.
- **Root Cause:**
  1. Zero-delay robotic behavior (PUT fired 7ms after login).
  2. Missing explicit `Authorization: Bearer <token>` in `slot_headers`.
  3. No cooling backoff or circuit-breaker on 403 Forbidden responses.
- **Fix Discovered & Applied:**
  Added 4–8s randomized humanized delay post-login, attached Bearer auth explicitly, replaced tight 3s retries with randomized backoff, and added a 12–20s cooling backoff with a 3-strike circuit breaker in `slot_monitor.py`.
- **Commit:** [`609bbbb`](https://github.com/KamalExpress/booking-agent/commit/609bbbb).

---

### INC-20260829-07: Weekend Polling Waste & Appointment Type Operating Day Misalignment
- **Severity:** `SEV-3 (Operational Inefficiency)`
- **Discovered At:** August 29, 2026 — 02:05 PKT
- **Observed Runtime Symptom:**
  Workers checked Saturdays and Sundays (when VACs are closed), wasting CAPTCHA tokens and proxy bandwidth. Furthermore, Code `26` was mistakenly checked on Thu/Fri only while Code `2` was checked all weekdays.
- **Root Cause:**
  Date generator lacked `weekday < 5` check and inverted the appointment type day mapping.
- **Fix Discovered & Applied:**
  Restricted date generation strictly to `weekday < 5` (Mon–Fri). Corrected mapping:
  - **National Visa Type D (Code 2):** Thursday & Friday only.
  - **Seasonal Type D (Code 26), Prime Time (Code 6), Premium Lounge (Code 5):** Monday through Friday.
- **Commit:** [`47c93ff`](https://github.com/KamalExpress/booking-agent/commit/47c93ff) & [`71d7be0`](https://github.com/KamalExpress/booking-agent/commit/71d7be0).
