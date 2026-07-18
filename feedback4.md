The overall direction is much stronger than a single worker pool, but there are a few architectural issues that will become painful later if you don't address them now.

## What I agree with

### 1. Dynamic scraper account rotation

Removing `scraper_account_id` from `Assignment` is the right decision.

An assignment should represent **work**, not **identity**.

Instead of:

```
Assignment
 ├── Center
 ├── Account A
```

it should become

```
Assignment
 ├── Center
 ├── Frequency
 ├── Priority
```

and the scheduler chooses whichever account is healthy.

This gives you:

* account rotation
* proxy rotation
* cooldowns
* future geographic routing

without changing assignments.

---

### 2. Separate scraper/booker pools

Absolutely.

They are fundamentally different systems.

Scrapers optimize for

* coverage
* polling frequency
* low detection

Bookers optimize for

* speed
* booking success
* minimizing burned accounts

Trying to merge them always ends in special cases everywhere.

---

### 3. BookingTask

Also the right direction.

I'd actually treat BookingTask as an event queue.

```
Scraper

↓

Slot Found Event

↓

BookingTask

↓

Booker
```

This completely decouples the two systems.

---

## Where I would change things

### 1. Don't overload ScraperAccount

This is the biggest thing I'd change.

Calling the table

```
ScraperAccount
```

while it stores booker accounts too will become confusing.

Rename it now.

```
PortalAccount
```

or

```
VisaAccount
```

Fields:

```
id

username

password

pool

proxy_id

status

cooldown_until

health_score

last_login

last_failure

failure_count

booking_count
```

Much cleaner.

---

### 2. Proxy should not be permanently assigned

This part worries me:

```
assigned_account_id
```

I'd remove it.

Instead

```
Proxy

id

host

port

username

password

pool

status

health_score

failure_count

last_used

cooldown_until
```

Then create

```
AccountProxyAssignment
```

only if you truly need permanent bindings.

Most systems don't.

Usually scheduler just says

```
Need scraper account

↓

Need scraper proxy

↓

Combine

↓

Run

↓

Release
```

That gives maximum flexibility.

---

### 3. Health is more important than status

Instead of only

```
Active

Disabled
```

I'd have

```
status

health_score

failure_count

last_success

last_failure

cooldown_until
```

Example

```
Proxy A

health = 98

Proxy B

health = 20

Proxy C

cooldown until tomorrow
```

Scheduler naturally prefers A.

---

### 4. BookingTask needs more metadata

Current:

```
visa_center

target_date

target_time
```

I'd add

```
tenant_id

assignment_id

slot_payload

priority

expires_at

attempts

max_attempts

last_error

created_by_worker

status
```

Remember:

A slot is time-sensitive.

After five minutes it might not exist anymore.

Tasks should expire automatically.

---

### 5. Slot deduplication

Imagine

20 scrapers

all detect

```
July 22
10:00
```

You don't want

20 BookingTasks.

You want

one.

I'd have a uniqueness rule like

```
Center

Date

Time

Tenant
```

If already pending

ignore duplicate.

---

### 6. Cooldowns should be strategy-based

Instead of

```
15 minutes

3 days
```

hardcoded,

I'd store

```
CooldownPolicy

Pool

Reason

Duration
```

Examples

```
Successful scrape

10 min

Captcha failure

45 min

Login failure

2 hr

Booked 5 appointments

3 days

HTTP 429

1 hr
```

Then scheduler applies policy.

Much easier to tune.

---

### 7. Booking count shouldn't be lifetime

Instead of

```
slots_booked_count
```

I'd use

```
booking_window_count

booking_window_start
```

or simply

```
bookings_since_last_reset
```

Otherwise you'll eventually need

```
UPDATE

SET count = 0
```

which is messy.

---

### 8. Worker pools deserve capabilities

Instead of

```
worker.pool = scraper
```

I'd lean toward capability flags:

```
can_scrape

can_book

can_login

can_rotate_proxy

supports_browser_profile
```

Later you may introduce hybrid workers or specialized hardware without changing the model.

---

## One thing missing completely

The scheduler.

Right now everything still sounds worker-driven.

I'd make the server the brain.

```
Scheduler

↓

Need scraper

↓

Choose assignment

↓

Choose account

↓

Choose proxy

↓

Create lease

↓

Worker polls

↓

Executes

↓

Returns
```

Workers should never decide

* which account
* which proxy
* which assignment

They simply execute leases.

That keeps all intelligence centralized.

---

## My recommended architecture

```
Assignments
        │
        ▼
 Scheduler
        │
        ├──────────────┐
        ▼              ▼
Portal Accounts     Proxies
        │              │
        └──────┬───────┘
               ▼
            Lease
               ▼
            Worker
               ▼
          SLOT_FOUND
               ▼
          BookingTask
               ▼
        Scheduler
               ▼
      Booker Account
               ▼
      Booker Proxy
               ▼
          Booker Worker
               ▼
          Booking Result
```

This keeps each component focused on a single responsibility and makes future additions—such as multiple visa portals, regional proxy pools, smarter health scoring, or different scheduling strategies—much easier without major refactoring.
