# Operational Guidance Glossary

This document serves as the master dictionary for all operational events, errors, and scheduler decisions within the platform. Every event listed here must follow the **Explain, Diagnose & Recover (EDR)** standard.

## Scheduler Decisions (Decision Type)

| Code | What Happened | Why did it happen? | How to fix it | Auto-Recovery |
| --- | --- | --- | --- | --- |
| `SUCCESS` | A worker was successfully leased. | The scheduler found a matching task, account, and proxy. | N/A | N/A |
| `NO_READY_ACCOUNT` | No portal account is available. | All capable accounts are either cooling down, disabled, or leased. | Add new accounts, enable disabled accounts, or wait for cooldowns to expire. | Yes, when cooldowns expire. |
| `NO_READY_PROXY` | No proxy is currently available. | All capable proxies are either cooling down, disabled, or leased. | Add new proxies or wait for cooldowns to expire. | Yes, when cooldowns expire. |
| `NO_READY_WORKER` | No worker was available to accept the task. | No worker with the necessary capabilities polled the server. | Ensure workers are running and properly configured with correct capabilities. | Yes, when a worker connects. |
| `NO_ASSIGNMENT` | No scraping tasks need to be run. | All assignments are currently leased or paused. | Create a new assignment or wait for the polling interval to lapse. | Yes, automatically when polling interval is due. |
| `NO_BOOKING_TASK` | No booking tasks are available. | No slots have been found recently by the scrapers. | Wait for scrapers to find slots. | Yes, automatically on `SLOT_FOUND`. |
| `LEASE_CONFLICT` | Stale lease update rejected. | A worker attempted to update a lease that had already expired or been reassigned. | Check worker internet connection and ensure it is returning results before lease TTL expires. | Worker will request a fresh lease. |

## Portal Events & Worker Logs (Event Type)

| Code | What Happened | Why did it happen? | How to fix it | Auto-Recovery |
| --- | --- | --- | --- | --- |
| `SLOT_FOUND` | An available appointment slot was detected. | A scraper successfully checked the portal and found availability. | N/A | N/A |
| `NO_SLOTS_FOUND` | No slots were available. | A scraper successfully checked the portal and found no availability. | N/A | N/A |
| `LOGIN_SUCCESS` | Worker logged into the visa portal successfully. | Credentials and proxy were accepted. | N/A | N/A |
| `LOGIN_FAILED` | The portal rejected the login. | Incorrect credentials, or the account is temporarily blocked by the portal. | Verify credentials. | Account will enter cooldown and retry later. |
| `CAPTCHA_FAILED` | Captcha could not be bypassed. | CapSolver/NopeCha failed to return a valid token in time. | Check your captcha solving provider balance or configuration. | Proxy and Account will retry on next lease. |
| `PROXY_TIMEOUT` | The worker could not reach the visa portal. | The assigned proxy is dead, too slow, or blocked by the portal's WAF. | Replace the proxy if it consistently times out. | Proxy enters cooldown; worker gets a different proxy next time. |
| `PORTAL_ERROR` | The visa portal returned a server error (5xx). | The visa portal is undergoing maintenance or is overloaded. | Wait for the portal to recover. | System will keep trying at the configured polling interval. |
| `BOOKING_FAILED` | A booking attempt failed. | The slot was taken by someone else before the booker could finish, or a portal error occurred during submission. | None (slot is lost). | Bookers will wait for the next `SLOT_FOUND` event. |
| `RATE_LIMITED` | The portal rate-limited the worker (429). | The proxy or account made too many requests in a short time. | Increase your polling interval or add more proxies. | Both Account and Proxy enter cooldown. |
| `WAF_TARPIT` | Worker network request hangs and times out after exactly 30s. | Imperva WAF dropped the POST packet because JS cookies expired, rather than sending a TCP reset. | Spawn a headless Playwright instance to evaluate the JS challenge and refresh cookies. | Yes, the worker detects the `curl: (28)` error and automatically triggers a cookie refresh. |
| `WAF_FINGERPRINT_MISMATCH` | Worker receives `403 Forbidden` despite valid cookies. | The browser fingerprint (User-Agent/sec-ch-ua) used to solve the JS challenge differs from the API scraper client. | Align Playwright context attributes perfectly with the `curl_cffi` impersonation profile. | No, requires developer intervention to fix the fingerprint alignment. |

## System / Lifecycle Events

| Code | What Happened | Why did it happen? | How to fix it | Auto-Recovery |
| --- | --- | --- | --- | --- |
| `WORKER_REGISTERED` | A new worker node connected. | A worker successfully started and contacted the SaaS. | N/A | N/A |
| `WORKER_OFFLINE` | A worker was marked offline. | The worker missed its heartbeat check (90s). | Restart the worker node if it crashed or check network connectivity. | Yes, when the worker reconnects. |
| `LEASE_CREATED` | A lease was issued to a worker. | The scheduler bundled a task, account, and proxy. | N/A | N/A |
| `LEASE_COMPLETED` | A lease was successfully finished. | The worker finished its task and reported back. | N/A | N/A |
| `LEASE_CANCELLED` | A lease was explicitly cancelled. | An admin manually cancelled the lease via the UI, or the system paused it. | N/A | N/A |
| `LEASE_EXPIRED` | A lease expired before completion. | The worker took too long to complete the task or died without sending a heartbeat. | Ensure worker instances have sufficient resources to complete tasks within TTL. | The task will be instantly re-queued for another worker. |
| `LEASE_ABANDONED` | A lease was marked abandoned. | The worker died or missed heartbeats, and its active leases were forcefully reclaimed by maintenance. | Restart the worker node if it crashed, or check network connectivity. | Yes, the task is re-queued and resources are freed. |
| `PUSH_SENT` | A Web Push payload was dispatched. | A booking task triggered an admin notification. | N/A | N/A |

## Entity Statuses (Portal Accounts, Proxies, Workers)

| Code | What Happened | Why did it happen? | How to fix it | Auto-Recovery |
| --- | --- | --- | --- | --- |
| `BLOCKED` | This entity is blocked and cannot be used. | It encountered a fatal error (like a permanent ban or invalid credentials) or was manually disabled. | Review the logs, update credentials, or manually unblock it. | No. Requires manual intervention. |
| `DISABLED` | This entity has been manually disabled. | An administrator toggled it off to prevent the scheduler from using it. | Re-enable it from the dashboard if you want it to be leased again. | No. |
| `COOLDOWN` | This entity is temporarily resting. | It was recently used or encountered a soft error (like a timeout or rate limit). | Wait for the cooldown period to expire. | Yes. It will become READY automatically. |
| `READY` | This entity is ready to be used. | It is healthy and currently available for the scheduler. | N/A | N/A |
| `LEASED` | This entity is currently in use. | The scheduler has assigned it to a worker node for a task. | N/A | It will return to READY or COOLDOWN when the task finishes. |
| `IDLE` | This entity is idle and waiting for work. | It is connected and healthy, but the scheduler hasn't assigned it a task yet. | N/A | N/A |
| `WORKING` | This entity is currently executing a task. | It received a lease from the scheduler and is actively processing it. | N/A | It will return to IDLE when the task completes. |
| `OFFLINE` | This entity is disconnected. | It missed its heartbeat check (likely crashed or lost internet connection). | Check the node's process logs, restart the node. | It will automatically recover when it reconnects. |

## Worker Node Terminology (System-Wide Roles)

| Role | Capabilities | Primary Function |
| --- | --- | --- |
| **Slot Agent** | `can_scrape=True, can_book=False` | Dedicated polling worker optimizing for continuous visa portal monitoring and low detection. Emits `SLOT_FOUND` events. |
| **Booking Agent** | `can_scrape=False, can_book=True` | Reactive, high-priority execution worker that acts immediately upon `BookingTask` creation to complete visa bookings. |
| **Dual Agent** | `can_scrape=True, can_book=True` | Hybrid worker capable of executing both continuous slot monitoring and reactive booking leases. |

## Production Incident & Hotfix Dictionary (August 28, 2026)

| Error Signature | What Happened | Why did it happen? | How to fix it | Auto-Recovery |
| --- | --- | --- | --- | --- |
| `UnboundLocalError: cannot access local variable 'Lease'` in `submit_logs` | Worker `/api/v1/worker/logs` failed with HTTP 500 on `SLOT_FOUND` or any log with `assignment_id`. Notifications and waitlist dispatches were blocked. | An inner import `from models import ... Lease` inside a conditional block caused Python to treat `Lease` as an unassigned local variable at the top of the function. | Promoted `Lease`, `SlotAvailability`, `BookingTask`, and all models to module-level imports. Initialized `lease = None` at function entry. | Fixed via commit `6de7ff8` (`prod`) and `c3a6289` (`staging`). |
| `AttributeError: 'dict' object has no attribute 'portal_account_id'` in `get_next_assignment` | Worker `/api/v1/worker/assignments/next` failed with HTTP 500 when recovering an existing active lease. | `get_existing_lease_for_worker` was returning a serialized dictionary while the router expected a SQLAlchemy `Lease` model instance. | Updated `get_existing_lease_for_worker` to return the `Lease` model instance directly. Guarded attribute queries. | Fixed via commit `810529d` (`prod`) and `4524f6e` (`staging`). |
| `TypeError: SchedulerService.auto_dispatch_queue() missing 2 required positional arguments` | Worker `/api/v1/worker/logs` failed with HTTP 500 inside `scheduler.handle_event`. | Legacy call in `handle_event` invoked `self.auto_dispatch_queue(visa_center, slot_count)`, but the method required `(visa_center, slots, assignment_id, target_date)`. | Made `auto_dispatch_queue` arguments flexible (`slots=None, assignment_id=None, target_date=None`) and removed the duplicate broken call in `handle_event`. | Fixed via commit `2ea89be` (`prod`) and current commit (`staging`). |
| `WAF_HEADER_ANOMALY (Imperva B10)` | Portal returns HTTP 200 with `<html...<script src="/_Incapsula_Resource?...">` and header `x-iinfo: ... B10(...)`. Worker reports `Login failed or blocked`. | Top-level GET preflight sent `Origin` and `Accept: application/json`, which Chrome never sends on document navigations. Imperva triggered Bot Rule B10 and tainted the TCP session. | Stripped `Origin` on GET, set `Accept: text/html...`, `Sec-Fetch-Site: none`, `Sec-Fetch-User: ?1`, and `Upgrade-Insecure-Requests: 1`. Set `Referer: .../login` and `Content-Type: application/json; charset=UTF-8`. | Fixed via commit `ad86281` (`staging`) and `17db917` (`prod`). |
| `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x80` in `load_session` | Worker threw warning `Could not load previous session` and repeatedly attempted fresh unauthenticated logins. | Session file on disk was persisted using Python's binary `pickle` in earlier builds. `json.load()` failed on the `0x80` pickle protocol header. | Updated `load_session()` to attempt `json.load()` with automatic fallback to `pickle.load()`. | Fixed via commit `e46ea54` (`staging`) and `17db917` (`prod`). |
| `WEEKEND_SCHEDULE_FILTER` | Staff reported workers checking Saturdays and Sundays, which are off. | Date generator looped `current_date += timedelta(days=1)` across all calendar days without checking `weekday`. | Filtered all date ranges with `weekday < 5` (Monday to Friday only). Prioritized Thursday & Friday for Greek Type D (26). | Fixed via commit `be6554c` (`staging`) and `47c93ff` (`prod`). |
| `ORPHAN_RESOURCE_RECONCILED` | Accounts or proxies stuck in `LEASED` status when no active lease existed. | Worker was disabled or timed out before cleanly executing the release hook. | Added `_reconcile_orphan_resources()` in `MaintenanceService.run_cleanup_cycle()` to auto-restore orphaned accounts/proxies to `READY`/`Active`. | Fixed via commit `f42b943` (`prod`) and `231d8c1` (`staging`). |


