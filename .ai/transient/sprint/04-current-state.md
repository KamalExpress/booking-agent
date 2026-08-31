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
- **Appointment Type Operating Days Mapping & Weekend Exclusion:**
  - Strictly filtered out weekends (`weekday < 5`), ensuring workers never check Saturdays or Sundays.
  - **Code `2` (National Visa Long Term Type D):** Operates on **Thursday & Friday** only (`weekday in [3, 4]`).
  - **Code `26` (Seasonal/Dependent Employment Type D):** Operates across all weekdays (**Monday through Friday**).
  - **Code `6` (Prime Time):** Operates across all weekdays (**Monday through Friday**).
  - **Code `5` (Premium Lounge):** Operates across all weekdays (**Monday through Friday**).
  - **Code `0` (Submission Schengen Visa Short Term Type C):** Remains an exception and is NOT targeted normally.

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

## 3. Production & Staging Restoration Milestones (August 31, 2026)

- **Production Restored on VPS:** Deployed target branch `feature/prod-july2026` on production VPS (`keagent.alamiaconnect.com`), cleanly restoring the last known working state observed by client staff (Commit `eaad857`, July 28, 2026).
- **Staging Restored on VPS:** Deployed target branch `feature/staging-july2026` on staging VPS (`staging.alamiaconnect.com`) at commit `eaad857`.
- **August Fixes Preserved:** Dedicated branches `feature/prod-aug2026` (Commit `04606ee`) and `feature/staging-aug2026` (Commit `0ad181b`) permanently store all August 28/29 hotfixes.
- **Architectural Divergence Recorded:** Documented in `.ai/permanent/architecture/08-staging-vs-production-architecture-divergence.md` that Staging contains the refactored **Execution Plane Abstraction**, **Adapter Factory**, **Multi-Provider Architecture**, **AI OCR Service**, and **Client Directory**, which were intentionally not deployed to production.

---

## 4. Pending Work / Next Session Objectives
1. **Phased Integration of August 28/29 Fixes:** Review `.ai/permanent/architecture/07-august-2026-hotfixes-audit.md` and plan the phased integration of essential SaaS bug fixes and WAF evasion into staging first.
2. **SaaS Admin UI for Appointment Type(s) - Days Mapping:** Implement a dynamic configuration UI in SaaS Admin (under `/settings` or `/assignments`) allowing staff to configure which appointment types (`2`, `26`, `6`, `5`, etc.) map to which active days of the week, replacing hardcoded rules.
3. **Live Slot Availability Calendar & Peak-Drop Board:** Implement the real-time calendar heatmap and live ticker dashboard (detailed in `.ai/permanent/workflows/09-live-slot-availability-calendar-board.md`) displaying open dates, times, and capacity during slot drops so staff can target exact slots for manual bookings without blind trial-and-error.
4. **Dynamic Regional Domain Failover (Control Plane):** Implement dynamic failover in the SaaS Scheduler to route worker leases to `https://bd-gr-services.gvcworld.eu` during high-traffic Pakistan slot drop windows.
5. **Passport OCR Orientation Enhancements (Deferred backlog):** Enhance passport preprocessing to handle skewed orientations and low-contrast prints.

---
*Branch State: VPS tracking feature/prod-july2026 & feature/staging-july2026 (eaad857) | August heads preserved on *-aug2026 | Date: 2026-08-31 14:15 PKT*
