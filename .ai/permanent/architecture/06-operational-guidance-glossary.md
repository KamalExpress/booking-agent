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
| `BOOKING_DISPATCHED` | An applicant in the queue was matched to a discovered slot and a BookingTask was created. | `SLOT_FOUND` occurred with waiting applicants matching the VAC and date criteria. | N/A | N/A |
| `BOOKING_CLAIMED` | A Booking Agent claimed the BookingTask and locked credentials. | A Booker worker polled the scheduler and leased the task. | N/A | N/A |
| `OTP_RECEIVED` / `OTP_INTERCEPTED` | An SMS or Email OTP verification code was captured. | GVC sent an OTP challenge during booking, which was captured via webhook or injected. | N/A | N/A |
| `BOOKING_SUCCESS` | An appointment was successfully booked and confirmed on GVC. | Booker completed form submission, OTP validation, and received a reference number. | N/A | Queue item marked BOOKED. |
| `BOOKING_ALREADY_EXISTS` | Booking rejected because applicant already has an active appointment. | Duplicate booking attempt for a passport number with an existing slot. | Mark queue entry as COMPLETED/CANCELLED. | Yes, Watchdog auto-resolves. |
| `WAF_CHALLENGE` | Portal WAF intercepted request with a JavaScript/Turnstile challenge (HTTP 403). | Missing valid TLS clearance token or high-frequency automated POST detected by Cloudflare/Imperva. | Verify browser persona alignment, proxy quality, or refresh clearance session. | Auto-retry with jitter; escalate to manual browser session if persistent. |
| `QUEUE_ENQUEUED` | Applicant added to waitlist queue. | User or API enqueued an applicant for slot matching. | N/A | N/A |
| `QUEUE_REMOVED` | Applicant removed from waitlist queue. | Admin deleted the queue entry. | N/A | N/A |
| `QUEUE_RESET` | Stuck or failed queue entry returned to PENDING. | Watchdog or Admin reset stuck tasks to allow re-dispatch. | N/A | Yes, auto-recovered by Watchdog. |
| `ASSIGNMENT_RESCHEDULED`| Monitoring assignment timer set to 0. | Admin or Watchdog surged assignment for immediate polling. | N/A | N/A |
| `PUSH_SENT` | A Web Push payload was dispatched. | A booking task or slot finding triggered an admin notification. | N/A | N/A |

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
