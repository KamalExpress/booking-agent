# Session Handoff - 2026-08-29 (Live Slots Release Window & Production Hardening)

## 1. Executive Summary & Session Context
During live production testing during an active GVC slot opening window, the team verified real-world slot detection, web push notifications, and automated booking behavior. Multiple critical edge cases, WAF challenge interception behaviors, PostgreSQL locking anomalies, and proxy hammering dynamics were analyzed, diagnosed, and resolved across both `feature/staging` and `feature/prod`.

---

## 2. Work Completed in This Session

### A. Production WAF & Login Evasion (Imperva Incapsula)
- **Eliminated Imperva Rule B10 Anomaly:**
  - Analyzed captured browser HAR files (`complete-booking-workflow-with-wrong-otp.har`) vs worker network logs.
  - Discovered that top-level GET preflight sent `Origin` and `Accept: application/json`, triggering Imperva Bot Rule B10 (`x-iinfo: ... B10`) and tainting subsequent requests with a 212-byte HTML JS challenge on HTTP 200.
  - Aligned preflight headers (`Accept: text/html...`, `Sec-Fetch-Site: none`, `Sec-Fetch-User: ?1`, `Upgrade-Insecure-Requests: 1`) and stripped `Origin` on all GET navigations.
- **Embedded Playwright WAF Challenge Solver:**
  - Configured `main_operator.py` and `core/adapters/gvc_adapter.py` to detect Imperva's HTML challenge on HTTP 200 during login and slot searches.
  - When detected, headless Playwright with stealth automatically navigates over the assigned Decodo proxy, computes the `_Incapsula_Resource` JS challenge, extracts 4 trust cookies (`incap_ses_*`, `visid_incap_*`), and injects them into the `curl_cffi` session.
  - Live logs confirmed: *"Login form detected! WAF challenge successfully bypassed. Successfully refreshed 4 WAF cookies. Login successful! Extracted and configured JWT Bearer token."*
- **Synchronized Booker Agent (`GVCAdapter`):**
  - Completely updated `ttttt/operator-agent/core/adapters/gvc_adapter.py` to match `main_operator.py`, enabling the staging Booker container to pass WAF and authenticate reliably.

### B. Scheduler & Waitlist Queue Dispatch Hardening
- **Decoupled Queue Dispatcher from Assignment Lookups:**
  - In `worker.py:submit_logs()`, `auto_dispatch_queue` was previously nested inside `if req.assignment_id: if assignment:`. If the assignment was archived or altered, dispatching never ran. Decoupled both `SlotAvailability` persistence and `auto_dispatch_queue` so slot drops always trigger applicant dispatch.
- **Resolved PostgreSQL Row Lock Trap:**
  - Removed `with_for_update(skip_locked=True)` on joined `WaitlistQueue` / `Applicant` queries, which caused PostgreSQL to return empty results if any concurrent query touched the applicants table.
- **Stale `BookingTask` Auto-Expiration:**
  - Added automatic expiration in `auto_dispatch_queue` for any tasks exceeding their TTL (`expires_at < now`), unlocking waitlisted applicants whose phone numbers were stuck in `active_locks`.
- **Added Comprehensive Logging:**
  - Logged each stage of queue dispatching, including skipped applicants, phone locks, and created task IDs.

### C. Operational Pacing & 403 Rate Limit Backoff
- **Humanized Post-Login Delay:**
  - Introduced a randomized 4.0s - 8.0s humanized pacing delay after login before the first slot search to prevent 0ms robotic behavior blocks.
- **Explicit Bearer Auth on Slot Search:**
  - Attached `Authorization: Bearer <token>` explicitly to `slot_headers` on `PUT /api/v1/periodslot/slots`.
- **Consecutive 403 Cooling Intervals:**
  - Replaced tight 3-second retries with randomized backoff delays (`random.uniform(5, 10) * (attempt + 1)`).
  - Added a streak counter in `slot_monitor.py`: if 403 is encountered, the worker applies a 12s - 20s cooling backoff, and pauses the run after 3 consecutive 403s to protect proxy reputation.
- **Strict Weekend Exclusion Filter:**
  - Filtered date generation across all 365 calendar days with `weekday < 5` (Monday to Friday only), preventing checks on Saturdays and Sundays.

### D. Multi-Provider Schema & Method Signature Compatibility
- **Resilient Scoring Policy:**
  - Updated `score_proxy` and `score_account` in `scoring_policy.py` with default values and `*args, **kwargs` to prevent `TypeError` when callers pass 1 or 2 positional arguments.
  - Used `getattr(account, 'provider_health', None)` and `getattr(proxy, 'provider_health', None)` so code runs smoothly on production without requiring unmigrated database columns.

### E. Architecture Knowledge & Cross-Regional Routing Documentation
- Documented cross-regional domain routing (`bd-gr-services.gvcworld.eu` load-shedding strategy) in `.ai/lessons/regional-domain-routing-evasion.md`.
- Updated `.ai/permanent/architecture/06-operational-guidance-glossary.md` with all recent production incidents, diagnostic signatures, and EDR guidance.

### F. Live Production Verification (Milestone Achieved)
- **Live Slot Notifications Restored & Confirmed:**
  - Following the deployment of the schema compatibility fix (`b072184`), the production SaaS server cleanly resolved the `TypeError` and `AttributeError`, allowing `/api/v1/worker/assignments/next` to lease assignments without errors.
  - Workers executed slot searches with the newly implemented humanized pacing and WAF solver, successfully detected open slots on the portal, and live Web Push notifications resumed delivering reliably to all tenant admins and staff.

---

## 3. Production Checkpoint & Rollback Pointers

To satisfy the user requirement of securing production to a known working state while preserving all fixes, two Git tags have been pushed to `origin`:

1. **`checkpoint-prod-notifications-6de7ff8`**:
   - **Commit:** `6de7ff8`
   - **State:** The earlier point where push notifications were first successfully received on production (`Aug 29, 00:14:56 PUSH_SENT`).
   - **Rollback Command (if desired):** `git checkout checkpoint-prod-notifications-6de7ff8`
2. **`checkpoint-prod-waf-fixes-b072184` (Current Head of `feature/prod`):**
   - **Commit:** `b072184`
   - **State:** Contains all WAF challenge bypasses (Playwright WAF solver), queue auto-dispatch fixes, weekend exclusion, post-login pacing delay, 403 backoff, and schema attribute safety.
   - **Deployment Command:** `git checkout feature/prod && git pull origin feature/prod`

---

## 4. Pending Work / Next Session Objectives
1. **Live Booking Validation:** Monitor the next live slot opening with the updated `auto_dispatch_queue` to observe automatic creation of `BookingTask` and verify the booker worker executes the end-to-end OTP booking flow.
2. **Dynamic Regional Domain Failover (Control Plane):** Implement dynamic failover in the SaaS Scheduler to route worker leases to `https://bd-gr-services.gvcworld.eu` during high-traffic Pakistan slot drop windows.
3. **Passport OCR Orientation Enhancements (Deferred backlog):** Enhance passport preprocessing to handle skewed orientations and low-contrast prints.

---
*Branch State: feature/staging & feature/prod synchronized | Date: 2026-08-29 02:00 PKT*
