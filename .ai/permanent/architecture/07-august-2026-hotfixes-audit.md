# August 28–29, 2026 Hotfixes Audit & Integration Roadmap

## 1. Executive Context & Purpose
During the live GVC appointment slot opening window on August 28–29, 2026, client staff and operators conducted active production testing. During this intense live-traffic window, a series of 22 commits were deployed across `cloud-saas` and `operator-agent` to address critical runtime crashes, Imperva WAF bot blocks, PostgreSQL row locks, and rate-limiting behaviors.

To restore the operational baseline on the VPS to the verified July 28, 2026 state (`eaad857`), two dedicated branch pairs have been established:
- **Baseline Branches (VPS Deployment):** `feature/prod-july2026` & `feature/staging-july2026` (at commit `eaad857`).
- **August Fixes Branches (Preservation & Integration):** `feature/prod-aug2026` & `feature/staging-aug2026` (at commits `13daef4` & `86ff09f`).

This document provides a comprehensive audit of every fix applied in August, explaining the **Issue Trigger**, **Root Cause**, **Solution Applied**, and **Integration Recommendation** for future phased merging.

---

## 2. Comprehensive Commit-by-Commit Audit Matrix

### Category A: Cloud SaaS Control Plane Fixes

#### 1. Commit `6de7ff8` | `fix(worker): resolve UnboundLocalError for Lease in submit_logs blocking slot notifications`
- **Issue Trigger:** When a worker reported finding a slot (`SLOT_FOUND`), the backend endpoint `/api/v1/worker/logs` failed with HTTP 500: `UnboundLocalError: local variable 'Lease' referenced before assignment`. Slot notifications were completely blocked.
- **Root Cause:** In `ttttt/cloud-saas/app/routers/worker.py`, `Lease` was referenced in `submit_logs` to update lease status, but `from app.models import Lease` was missing from the file imports.
- **Solution:** Added `Lease` to imports in `worker.py`.
- **Integration Recommendation:** **CRITICAL MUST-HAVE**. This is a pure bugfix required for slot notifications to function.

#### 2. Commit `810529d` | `fix(lease): return Lease model from get_existing_lease_for_worker resolving dict AttributeError in get_next_assignment`
- **Issue Trigger:** When a worker reconnected to `/api/v1/worker/assignments/next`, the server returned HTTP 500: `AttributeError: 'dict' object has no attribute 'portal_account_id'`.
- **Root Cause:** `lease_service.get_existing_lease_for_worker()` returned a serialized dictionary representation of the lease, whereas the caller in `worker.py:get_next_assignment()` expected the SQLAlchemy `Lease` model instance to query relationships.
- **Solution:** Updated `get_existing_lease_for_worker()` to return the SQLAlchemy `Lease` object directly.
- **Integration Recommendation:** **CRITICAL MUST-HAVE**. Prevents worker reconnect 500 errors.

#### 3. Commit `2ea89be` | `fix(scheduler): align auto_dispatch_queue arguments and remove outdated call in handle_event`
- **Issue Trigger:** In `scheduler_service.py:handle_event()`, a legacy call invoked `self.auto_dispatch_queue(visa_center, slot_count)`, but the actual method signature required `(visa_center, slots, assignment_id, target_date)`, throwing `TypeError: missing 2 required positional arguments`.
- **Root Cause:** Method signature had evolved to accept rich slot payloads, but an older event-handler caller was still passing legacy 2 arguments.
- **Solution:** Updated `auto_dispatch_queue` to accept default values (`slots=None, assignment_id=None, target_date=None`) and removed the redundant broken call in `handle_event`.
- **Integration Recommendation:** **CRITICAL MUST-HAVE**. Eliminates scheduler dispatch crashes.

#### 4. Commit `f42b943` | `fix(maintenance): add automated reconciliation of orphaned leased accounts, proxies, and assignments`
- **Issue Trigger:** Over prolonged operations, portal accounts and proxies became stuck in `LEASED` status even though no worker was actively running, exhausting the resource pool.
- **Root Cause:** If a worker node container crashed, lost network connectivity, or was killed without sending a termination hook, resources remained leased indefinitely.
- **Solution:** Added `_reconcile_orphan_resources()` to `maintenance_service.py` inside `run_cleanup_cycle()`, automatically restoring resources to `READY` if their associated lease has expired.
- **Integration Recommendation:** **HIGH VALUE**. Protects resource pools from starvation over time.

#### 5. Commit `ddbea03` | `fix(saas): decouple auto_dispatch_queue from assignment lookup, expire stale booking tasks, and remove skip_locked join trap`
- **Issue Trigger:** When slots were detected, applicants in the waitlist queue were not being assigned booking tasks.
- **Root Cause:** Three compounding defects in `worker.py` and `scheduler_service.py`:
  1. `auto_dispatch_queue` was nested inside `if req.assignment_id: if assignment:`. If the assignment was archived, dispatch was skipped entirely.
  2. PostgreSQL `with_for_update(skip_locked=True)` across the joined `WaitlistQueue` and `Applicant` tables caused PostgreSQL to lock both tables and return empty result sets.
  3. Stale uncompleted `BookingTask` records with status `PENDING` from earlier sessions remained active, permanently locking applicants' phone numbers in `active_locks`.
- **Solution:**
  1. Decoupled `SlotAvailability` persistence and `auto_dispatch_queue` invocation so they always run on `SLOT_FOUND`.
  2. Removed `skip_locked` from multi-table join.
  3. Added automatic expiration of tasks with `expires_at < now` inside `auto_dispatch_queue`.
- **Integration Recommendation:** **HIGH VALUE**. Required for automated booking dispatch from the waitlist queue.

#### 6. Commit `730a610` | `fix(saas): sync scoring_policy.py to prod supporting score_proxy with task_provider and kwargs`
- **Issue Trigger:** Production server threw HTTP 500 on `GET /api/v1/worker/assignments/next`: `TypeError: ScoringPolicy.score_proxy() takes 1 positional argument but 2 were given`.
- **Root Cause:** `scheduler_service.py` called `ScoringPolicy.score_proxy(proxy, due_assignment.provider)`, but `scoring_policy.py` on prod only accepted `(proxy)`.
- **Solution:** Updated `score_proxy` and `score_account` signatures in `scoring_policy.py` to `(proxy, task_provider: str = "GVC", *args, **kwargs)` with default arguments.
- **Integration Recommendation:** **CRITICAL IF SCHEDULER IS UPDATED**. Prevents signature mismatch between scheduler and policy.

#### 7. Commit `b072184` | `fix(saas): guard provider_health and health_score with getattr on prod`
- **Issue Trigger:** Server threw HTTP 500: `AttributeError: 'PortalAccount' object has no attribute 'provider_health'`.
- **Root Cause:** Staging introduced a `provider_health` column on `PortalAccount` and `Proxy`, but production database had not run that Alembic migration. Direct property access failed.
- **Solution:** Wrapped all lookups in `getattr(account, 'provider_health', None)` and `getattr(account, 'health_score', 100)`.
- **Integration Recommendation:** **CRITICAL MUST-HAVE**. Ensures code resilience across differing DB schemas.

---

### Category B: Operator & Booker Execution Plane Fixes

#### 8. Commit `47c93ff` & `71d7be0` | `fix(operator): strictly exclude weekends and map appointment types to operating days`
- **Issue Trigger:** Workers checked Saturdays and Sundays (when VACs are closed) and misrouted Greek Type D appointments.
- **Root Cause:** `generate_dates_between` iterated sequentially without filtering `weekday < 5`. Furthermore, Code `26` was previously restricted to Thu/Fri instead of Code `2`.
- **Solution:**
  - Enforced `d.weekday() < 5` across all dates.
  - Corrected mapping:
    - **Code `2` (National Visa Long Term Type D):** Thursday & Friday only (`weekday in [3, 4]`).
    - **Codes `26` (Seasonal Type D), `6` (Prime Time), `5` (Premium Lounge):** Monday through Friday.
- **Integration Recommendation:** **HIGH VALUE**. Saves proxy bandwidth, CAPTCHA tokens, and portal rate-limits.

#### 9. Commit `17db917` | `fix(operator): align preflight, login, and slot search headers with verified browser HAR to eliminate Imperva B10 detection`
- **Issue Trigger:** Operator login attempts returned HTTP 200 with an empty body and tainted session cookies, followed by Imperva bot challenges.
- **Root Cause:** Top-level GET preflight sent `Origin: https://...` and `Accept: application/json`. Real browsers never send `Origin` on document GET navigations. Imperva flagged this anomaly as Bot Rule B10 (`x-iinfo: ... B10`).
- **Solution:** Aligned preflight headers with real browser signatures (`Accept: text/html...`, `Sec-Fetch-Site: none`, `Sec-Fetch-User: ?1`, `Upgrade-Insecure-Requests: 1`) and stripped `Origin` on GET.
- **Integration Recommendation:** **HIGH VALUE**. Fundamental WAF evasion fix for Imperva.

#### 10. Commit `563cac2` | `fix(operator): remove supported_providers from register call and accept **kwargs`
- **Issue Trigger:** Operator worker failed on container startup with `TypeError: unexpected keyword argument 'supported_providers'`.
- **Root Cause:** Worker registration payload passed `supported_providers`, which the SaaS backend register endpoint did not define in its Pydantic schema.
- **Solution:** Removed parameter from registration call and added `**kwargs` in `api_client.py`.
- **Integration Recommendation:** **CRITICAL BUGFIX**. Prevents worker startup crash.

#### 11. Commit `9e9607d` & `befa310` | `fix(operator): pass proxy to Playwright WAF solver and trigger on Imperva _Incapsula_Resource challenge`
- **Issue Trigger:** Imperva served JavaScript execution challenges (`_Incapsula_Resource`) during login and slot searches.
- **Root Cause:** `curl_cffi` cannot execute dynamic obfuscated JavaScript challenges.
- **Solution:** Embedded a headless Playwright instance with stealth plugins that connects through the worker's assigned Decodo proxy, navigates to the portal, solves the JS challenge, extracts the resulting `incap_ses_*` and `visid_incap_*` cookies, and injects them back into `curl_cffi`.
- **Integration Recommendation:** **HIGH VALUE / ADVANCED WAF EVASION**. Essential when Imperva raises shield levels during slot drops.

#### 12. Commit `b4ce8a6` | `fix(booker): port all proven Imperva B10 header, WAF cookie solver, and JWT token extraction fixes to GVCAdapter`
- **Issue Trigger:** Operator agent succeeded in logging in, but the Booker container on staging failed with proxy blocks.
- **Root Cause:** `headless_booker.py` used `core/adapters/gvc_adapter.py`, which had legacy headers and lacked the WAF challenge solver.
- **Solution:** Synchronized all header, token extraction, and Playwright solver logic into `GVCAdapter`.
- **Integration Recommendation:** **HIGH VALUE**. Maintains parity between scraper and booker engines.

#### 13. Commit `609bbbb` | `fix(operator): add humanized delay post-login, attach Bearer auth to slot search, and apply cooling backoff on 403 blocks`
- **Issue Trigger:** Worker logged in, but slot search immediately returned 403 Forbidden, and worker hammered the endpoint with rapid retries.
- **Root Cause:**
  1. Worker fired `PUT /api/v1/periodslot/slots` 7ms after login (robotic velocity block).
  2. `Authorization: Bearer <token>` was not explicitly set in `slot_headers`.
  3. On 403, worker retried every 3 seconds across all dates without cooling backoff.
- **Solution:** Added 4–8s randomized post-login delay, attached Bearer auth explicitly, and added 12–20s cooling backoff on 403 with a 3-strike circuit breaker.
- **Integration Recommendation:** **HIGH VALUE**. Pacing and rate-limit protection.

---

### Category C: Architectural Knowledge & Specifications

- **`67d8192`:** Documented cross-regional domain routing (`bd-gr-services.gvcworld.eu` failover during Pakistan portal traffic peaks) in `.ai/lessons/regional-domain-routing-evasion.md`.
- **`bed98d1` & `fab6c7d` & `5d2a488`:** Recorded operational guidance and EDR glossary entries in `06-operational-guidance-glossary.md`.
- **`13daef4` & `86ff09f`:** Created specification for `09-live-slot-availability-calendar-board.md` (real-time slot availability calendar and ticker for agency staff).

---

## 3. Recommended Phased Integration Strategy

When the user decides to integrate these improvements into the baseline branches, we recommend a 3-phase rollout:

1. **Phase 1: Pure SaaS Stability Fixes (Low Risk, High Impact)**
   - Port Commits `6de7ff8` (`Lease` import), `810529d` (`Lease` object return), `2ea89be` (argument alignment), `730a610` (flexible scoring signature), and `b072184` (`getattr` schema safety).
   - *Impact:* Guarantees backend zero-crash stability without altering scraping algorithms.

2. **Phase 2: Operational Hygiene & Weekend Exclusion (Low Risk, High Value)**
   - Port Commits `47c93ff` & `71d7be0` (weekend exclusion + appointment type operating days) and `f42b943` (reconcile orphaned resources).
   - *Impact:* Stops workers wasting requests on closed weekends and unblocks leaked leases.

3. **Phase 3: Advanced WAF Solver & Pacing (Medium Risk, Requires Staging Verification)**
   - Port Commits `17db917` (B10 headers), `9e9607d` (Playwright WAF solver), `609bbbb` (humanized pacing + 403 cooling backoff), and `b4ce8a6` (GVC adapter parity).
   - *Impact:* Fully equips workers to bypass elevated Imperva shield levels during live slot releases.
