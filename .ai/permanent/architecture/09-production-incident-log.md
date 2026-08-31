# Production Incident Log & Post-Mortem Register

## 1. Governance & Severity Taxonomy
This document serves as the formal **Production Incident Register** for the platform. Every runtime outage, notification failure, WAF block cascade, or schema incompatibility experienced on production or during live testing windows is cataloged here as an **Incident Record**.

### Severity Levels:
- **SEV-1 (Critical Outage):** Core operational capability completely down (e.g. notifications blocked, worker registration crashing, scheduler throwing 500s, automated booking halted).
- **SEV-2 (High Impact):** Subsystem degraded, worker reconnect failing, or resource pool leaking.
- **SEV-3 (Moderate Degradation):** Inefficient polling, unneeded weekend queries, or non-blocking telemetry gaps.

---

## 2. Active Slot Window Incidents (August 28–29, 2026)

### INC-20260828-01: Web Push Notifications Blocked by `UnboundLocalError: Lease`
- **Severity:** `SEV-1 (Critical Outage)`
- **Date & Time:** August 28, 2026 — 22:30 PKT
- **Symptom:** During an active slot release window, headless workers detected open slots and posted `SLOT_FOUND` events to `/api/v1/worker/logs`. The SaaS backend responded with **HTTP 500 Internal Server Error**. Admins and agency staff received zero Web Push notifications.
- **Root Cause:** Python bytecode scoping rule. An inner import statement `from models import ... Lease` inside `elif req.event_type == "SLOT_FOUND":` at line 375 caused the Python compiler to treat `Lease` as a local variable throughout the entire `submit_logs()` function. When execution reached line 295 (`db.query(Lease)`), line 375 had not executed, raising `UnboundLocalError: local variable 'Lease' referenced before assignment` and aborting before `send_push_notification()` could run.
- **Resolution:** Moved all model imports (`Lease`, `SlotAvailability`, `BookingTask`) to module-level imports at top of file, initialized `lease = None` at function entry, and eliminated the nested import.
- **Commit:** [`6de7ff8`](https://github.com/KamalExpress/booking-agent/commit/6de7ff8) / [`b763efb`](https://github.com/KamalExpress/booking-agent/commit/b763efb) on `feature/prod-july2026`.
- **Status:** **Resolved**.

---

### INC-20260828-02: Worker Lease Recovery 500 on `AttributeError: dict object`
- **Severity:** `SEV-2 (High Impact)`
- **Date & Time:** August 28, 2026 — 22:42 PKT
- **Symptom:** Workers reconnecting to `/api/v1/worker/assignments/next` received HTTP 500: `AttributeError: 'dict' object has no attribute 'portal_account_id'`.
- **Root Cause:** `lease_service.get_existing_lease_for_worker()` returned a serialized dictionary representation of the lease, whereas the router caller expected a SQLAlchemy `Lease` model instance to query relationships.
- **Resolution:** Updated `get_existing_lease_for_worker()` to return the `Lease` model instance directly.
- **Commit:** [`810529d`](https://github.com/KamalExpress/booking-agent/commit/810529d).
- **Status:** **Resolved**.

---

### INC-20260828-03: Scheduler Crash on Legacy `auto_dispatch_queue` Arguments
- **Severity:** `SEV-2 (High Impact)`
- **Date & Time:** August 28, 2026 — 22:45 PKT
- **Symptom:** Logging endpoint crashed inside `scheduler.handle_event` with `TypeError: auto_dispatch_queue missing 2 required positional arguments`.
- **Root Cause:** `auto_dispatch_queue` had been refactored to require rich slot information `(visa_center, slots, assignment_id, target_date)`, but a legacy call in `handle_event` only passed `(visa_center, slot_count)`.
- **Resolution:** Made arguments flexible with defaults (`slots=None, assignment_id=None, target_date=None`) and removed the duplicate broken call in `handle_event`.
- **Commit:** [`2ea89be`](https://github.com/KamalExpress/booking-agent/commit/2ea89be).
- **Status:** **Resolved**.

---

### INC-20260828-04: Resource Pool Starvation via Orphaned Leased Accounts & Proxies
- **Severity:** `SEV-2 (High Impact)`
- **Date & Time:** August 28, 2026 — 23:10 PKT
- **Symptom:** Portal accounts and proxies remained locked in `LEASED` status indefinitely after worker containers were restarted or dropped network connections, eventually exhausting the pool.
- **Root Cause:** If a worker node terminated abruptly without triggering an unlease hook, the database record remained `LEASED` until manually reset.
- **Resolution:** Implemented `_reconcile_orphan_resources()` in `maintenance_service.py` within the periodic background cleanup cycle to auto-reconcile resources whose leases have expired.
- **Commit:** [`f42b943`](https://github.com/KamalExpress/booking-agent/commit/f42b943).
- **Status:** **Resolved**.

---

### INC-20260829-01: Imperva Bot Rule B10 Detection via Document Navigation Header Anomaly
- **Severity:** `SEV-1 (Critical Outage)`
- **Date & Time:** August 29, 2026 — 00:20 PKT
- **Symptom:** Workers attempting to log in were blocked by Imperva with HTTP 200 containing a 212-byte JavaScript challenge (`/_Incapsula_Resource?...`). Header `x-iinfo: ... B10(...)` was returned and sessions were tainted.
- **Root Cause:** The worker sent `Origin: https://...` and `Accept: application/json` on top-level GET document navigations. Real Chrome desktop browsers never send `Origin` on document GET navigations. Imperva flagged this anomaly as Bot Rule B10.
- **Resolution:** Aligned headers with genuine browser signatures: stripped `Origin` on GET, configured `Accept: text/html...`, `Sec-Fetch-Site: none`, `Sec-Fetch-User: ?1`, and `Upgrade-Insecure-Requests: 1`.
- **Commit:** [`17db917`](https://github.com/KamalExpress/booking-agent/commit/17db917).
- **Status:** **Resolved (Preserved on August branch / Stage)**.

---

### INC-20260829-02: Operator Worker Container Crash on Unrecognized Schema Field
- **Severity:** `SEV-1 (Critical Outage)`
- **Date & Time:** August 29, 2026 — 00:34 PKT
- **Symptom:** Production operator container crashed on startup with `TypeError: unexpected keyword argument 'supported_providers'`.
- **Root Cause:** The worker registration API client sent `supported_providers`, which the SaaS backend registration endpoint did not accept in its schema.
- **Resolution:** Removed `supported_providers` from registration payload and added `**kwargs` resilience in `api_client.py`.
- **Commit:** [`563cac2`](https://github.com/KamalExpress/booking-agent/commit/563cac2).
- **Status:** **Resolved (Preserved on August branch / Stage)**.

---

### INC-20260829-03: Imperva Dynamic JS Challenge (`_Incapsula_Resource`) Interception
- **Severity:** `SEV-1 (Critical Outage)`
- **Date & Time:** August 29, 2026 — 00:38 PKT
- **Symptom:** During high traffic, Imperva served dynamic obfuscated JavaScript challenges (`_Incapsula_Resource`) during login and slot searches. `curl_cffi` was unable to execute JavaScript, failing authentication.
- **Root Cause:** Elevated Imperva threat level during quarterly slot opening required genuine browser JavaScript execution and client-side proof-of-work.
- **Resolution:** Configured headless Playwright with stealth plugins to route over the worker's assigned Decodo proxy, execute the JS challenge, extract the resulting `incap_ses_*` and `visid_incap_*` cookies, and inject them into `curl_cffi`.
- **Commit:** [`9e9607d`](https://github.com/KamalExpress/booking-agent/commit/9e9607d) & [`befa310`](https://github.com/KamalExpress/booking-agent/commit/befa310).
- **Status:** **Resolved (Preserved on August branch / Stage)**.

---

### INC-20260829-04: Account Rate-Limiting & Proxy Block via Rapid Consecutive 403 Hammering
- **Severity:** `SEV-1 (Critical Outage)`
- **Date & Time:** August 29, 2026 — 01:35 PKT
- **Symptom:** After logging in, workers received HTTP 403 Forbidden on `PUT /api/v1/periodslot/slots` and repeatedly hammered the endpoint every 3 seconds across all centers and dates, causing proxy reputation burn and portal bans.
- **Root Cause:**
  1. Zero-delay robotic behavior (PUT fired 7ms after login).
  2. Missing explicit `Authorization: Bearer <token>` in `slot_headers`.
  3. No cooling backoff or circuit-breaker on 403 Forbidden responses.
- **Resolution:** Added 4–8s randomized humanized delay post-login, attached Bearer auth explicitly, replaced tight 3s retries with randomized backoff, and added a 12–20s cooling backoff with a 3-strike circuit breaker in `slot_monitor.py`.
- **Commit:** [`609bbbb`](https://github.com/KamalExpress/booking-agent/commit/609bbbb).
- **Status:** **Resolved (Preserved on August branch / Stage)**.

---

### INC-20260829-05: Scheduler HTTP 500 on `TypeError: score_proxy` Signature Mismatch
- **Severity:** `SEV-1 (Critical Outage)`
- **Date & Time:** August 29, 2026 — 01:44 PKT
- **Symptom:** Production SaaS threw HTTP 500 on `/api/v1/worker/assignments/next`: `TypeError: ScoringPolicy.score_proxy() takes 1 positional argument but 2 were given`.
- **Root Cause:** `scheduler_service.py` was updated to pass `due_assignment.provider` to `score_proxy`, but `scoring_policy.py` on production expected only `(proxy)`.
- **Resolution:** Updated `score_proxy` and `score_account` signatures to accept optional `task_provider: str = "GVC"`, `*args`, and `**kwargs`.
- **Commit:** [`730a610`](https://github.com/KamalExpress/booking-agent/commit/730a610).
- **Status:** **Resolved (Preserved on August branch / Stage)**.

---

### INC-20260829-06: Production Server Crash on Missing `provider_health` Column
- **Severity:** `SEV-1 (Critical Outage)`
- **Date & Time:** August 29, 2026 — 01:50 PKT
- **Symptom:** Production SaaS threw HTTP 500 on assignment scheduling: `AttributeError: 'PortalAccount' object has no attribute 'provider_health'`.
- **Root Cause:** Multi-provider health tracking added on staging queried `account.provider_health`, but the production database had not run that Alembic migration. Direct property access threw `AttributeError`.
- **Resolution:** Guarded lookups using `getattr(account, 'provider_health', None)` and `getattr(account, 'health_score', 100)`.
- **Commit:** [`b072184`](https://github.com/KamalExpress/booking-agent/commit/b072184).
- **Status:** **Resolved (Preserved on August branch / Stage)**.
