This is now a much more solid architecture. I would be comfortable building on this because you've separated responsibilities cleanly and you're thinking about observability, concurrency, and scheduling from the start.

There are only a few things I'd change before calling it "Sprint 10 Final."

---

# 1. Don't use `role` for accounts and proxies

I'd actually keep `role` for workers, but for accounts and proxies I'd use **capabilities** or **purpose**.

For example:

```
PortalAccount

purpose:
    SCRAPE
    BOOK
```

or

```
supports_scraping = true
supports_booking = false
```

The reason is that six months from now you may have accounts that can both scrape and book, or different visa portals with different capabilities. A single enum becomes restrictive.

---

# 2. SchedulerDecision should log failures too

Right now it sounds like it only logs successful selections.

I'd log **every scheduling attempt**.

Example:

```
SchedulerDecision

decision_type

SUCCESS

NO_READY_ACCOUNT

NO_READY_PROXY

NO_READY_WORKER

NO_ASSIGNMENT

NO_BOOKING_TASK

LEASE_CONFLICT
```

Otherwise when workers report "No work available" you won't know why.

This table becomes your scheduler's black box recorder.

---

# 3. Don't rely only on READY status

Status is coarse.

Scheduler should filter on things like:

```
status == READY

AND

cooldown_until <= now

AND

enabled == true

AND

not leased

AND

credentials valid
```

Otherwise READY starts becoming overloaded.

---

# 4. BookingTask needs a unique constraint

Instead of just checking in code:

```
SELECT ...

if none found

INSERT
```

two scrapers can race.

I'd add a database unique constraint on something like:

```
tenant_id
visa_center
target_date
target_time
status_active
```

or another strategy that guarantees only one active task exists for the same slot. Code-level deduplication alone won't prevent races under concurrency.

---

# 5. Lease expiration

You mention versioning, but leases also need TTL.

Example:

```
issued_at

expires_at

heartbeat_at
```

Worker crashes?

Lease expires.

Scheduler reissues.

Without this, one dead worker can hold resources indefinitely.

---

# 6. Scheduler scoring should be pluggable

Today:

```
SchedulerScore(...)
```

Tomorrow you'll want to tweak it.

Instead of embedding formulas throughout the scheduler, centralize them:

```
ScoringPolicy

score_account()

score_proxy()

score_worker()

score_assignment()
```

That makes experimentation much easier.

---

# 7. Separate portal events from scheduling events

Right now you have:

```
LOGIN_FAILED

CAPTCHA_FAILED

RATE_LIMITED
```

Those are portal events.

Scheduler should translate them into scheduling actions.

For example:

```
Portal Event

↓

Scheduler Policy

↓

Cooldown
Score Penalty
Disable
Retry
Alert
```

Keeping these layers separate prevents the scheduler from becoming tightly coupled to one portal's behavior.

---

# 8. Think ahead for multiple visa providers

Your current schema is centered on a single portal.

If you think this platform might later support multiple appointment systems, add a provider dimension early:

```
PortalAccount

provider

GVC

VFS

BLS
```

Likewise for assignments and booking tasks. Adding it later is possible, but more invasive.

---

## Overall

This revision addresses the biggest architectural weaknesses from the earlier versions:

* Scheduler and lease management are now distinct.
* Accounts and proxies are dynamically paired.
* Cooldowns are resource-specific.
* Booking tasks are event-driven and traceable.
* Lease versioning prevents stale updates.
* Scheduler decisions are observable.

Let's avoid turning Sprint 10 into an endless architecture exercise. Build this foundation, validate it under load with a handful of scraper and booker workers, and let real operational data guide the next iteration.
