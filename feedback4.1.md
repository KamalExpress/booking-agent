This is significantly better. The architecture is now moving toward a real distributed scheduling platform rather than a collection of workers.

I still see a handful of things I'd address before implementation, because changing them later would be expensive.

---

# 1. Don't make LeaseService the Scheduler

This is mostly a naming issue.

Your plan says:

> `lease_service.py (The Scheduler Brain)`

I would separate these concepts.

```
SchedulerService
    decides WHAT should run

LeaseService
    creates / renews / expires leases
```

Example flow:

```
Worker polls

↓

SchedulerService.select_next_work()

↓

Assignment
BookingTask
PortalAccount
Proxy

↓

LeaseService.create_lease(...)

↓

Worker receives lease
```

Otherwise LeaseService will slowly become a 2000-line God object.

---

# 2. Health score shouldn't be manually updated

Instead of

```
health_score
```

being an arbitrary integer,

derive it.

For example:

```
Base = 100

-5 login failure

-10 captcha failure

-20 HTTP 429

-40 proxy timeout

+2 successful scrape

+10 successful booking
```

Health becomes a function of events.

Eventually you may not even store it.

You simply calculate

```
SchedulerScore
```

using

```
recent failures
recent successes
last use
cooldown
```

This produces much smarter scheduling.

---

# 3. Booking priority needs more than priority

Current

```
priority
```

I'd use

```
priority

expires_at

created_at
```

Scheduling algorithm

```
highest priority

↓

earliest expiration

↓

oldest creation
```

Otherwise two Priority 1 bookings have undefined ordering.

---

# 4. Don't search every account every lease

This becomes expensive.

Instead of

```
SELECT ...

ORDER BY health DESC
```

every worker poll,

maintain

```
AccountState

READY

LEASED

COOLDOWN

DISABLED
```

Scheduler only searches

```
READY
```

Same for proxies.

This becomes much faster with thousands of accounts.

---

# 5. Add lease versioning

Leases should contain

```
lease_id

lease_version

issued_at

expires_at
```

Worker completes

```
Lease 51 Version 3
```

If scheduler already revoked it and issued

```
Version 4
```

completion gets rejected.

Prevents stale workers overwriting newer state.

---

# 6. BookingTask needs ownership

Right now

```
tenant_id
```

is good.

I'd also include

```
assignment_id
```

because later you'll ask

> Which monitor generated this booking?

Without it, reporting becomes difficult.

---

# 7. Add failure reason enums

Instead of

```
last_error = string
```

I'd have

```
failure_reason

LOGIN_FAILED

CAPTCHA_FAILED

PROXY_TIMEOUT

PORTAL_ERROR

NO_SLOT

BOOKING_FAILED

RATE_LIMITED

UNKNOWN
```

and then optionally

```
failure_details
```

Scheduler should react to reasons differently.

---

# 8. Proxy cooldown shouldn't always equal account cooldown

Current wording implies

```
cooldown account

↓

same cooldown proxy
```

Those are independent.

Example

```
Captcha failed

↓

Account probably okay

↓

Proxy suspicious
```

versus

```
Wrong password

↓

Account cooldown

↓

Proxy perfectly healthy
```

Cooldown policies should be keyed by **resource** and **event**.

Example:

```
account.login_failure

proxy.http_429

proxy.timeout

account.booking_limit

account.booking_success

proxy.success
```

This gives much finer control.

---

# 9. Booking limits probably shouldn't reset immediately

Current

```
Reached 5

↓

3 day cooldown

↓

reset counter
```

I'd instead do

```
booking_window_start

bookings_in_window
```

If

```
window expired

↓

reset automatically
```

More flexible if tomorrow you change policy to

```
10 bookings

24 hours
```

instead of

```
5 bookings

3 days
```

---

# 10. Missing Scheduler audit log

This is the one thing I'd definitely add.

Every scheduling decision should be explainable.

Example

```
SchedulerDecision

id

worker

selected_assignment

selected_account

selected_proxy

decision_score

decision_reason

created_at
```

Later when someone asks

> Why was Account 47 chosen instead of Account 12?

you'll have an answer.

Otherwise debugging scheduling logic becomes extremely difficult.

---

# One additional future-proofing suggestion

Right now you have:

```
Scraper Pool

Booker Pool
```

I'd avoid hardcoding those values as enums throughout the codebase.

Instead, think in terms of **roles** or **capabilities**:

* `SCRAPER`
* `BOOKER`
* `LOGIN_ONLY`
* `OTP_REQUIRED`
* `HIGH_PRIORITY_BOOKER`

Even if you only use two today, this makes it much easier to introduce specialized account types later without another schema migration.

## Overall assessment

I'd consider this architecture **production-grade for an MVP** after incorporating the refinements above. The key strengths are:

* Centralized scheduling rather than worker-driven decisions.
* Complete separation of scraping and booking workflows.
* Dynamic pairing of accounts and proxies at lease time.
* Event-driven booking pipeline with deduplication.
* Configurable operational policies instead of hardcoded values.

The remaining improvements are mostly about scalability, observability, and making the scheduler easier to evolve as the platform grows from dozens of workers to hundreds or thousands.
