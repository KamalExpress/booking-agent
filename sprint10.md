I actually **wouldn't make Sprint 10 a feature sprint**.

I'd make it an **Architecture Hardening Sprint**.

Looking back over our conversations, your project has undergone a major evolution:

* Desktop GUI → Cloud SaaS
* Single operator → Distributed workers
* Browser sessions → Leases
* Simple bot → Browser automation platform
* Project docs → AI knowledge system

That's a lot of foundational change. Before adding more capabilities, I'd make sure the foundation is solid.

---

# Sprint 10 Theme

> **"Platform Hardening & Operational Excellence"**

The goal is **not** to add lots of user-visible features.

The goal is to ensure the platform can safely support Sprint 11–20.

---

# Epic 1 – Worker Lifecycle ⭐⭐⭐⭐⭐ (Highest Priority)

Right now the worker lifecycle is only partially implemented.

Complete it end-to-end.

### Stories

* Worker heartbeat expiration
* Graceful worker shutdown
* Worker reconnect handling
* Worker stale registration cleanup
* Worker capability refresh
* Worker health endpoint
* Worker lifecycle documentation (Mermaid)

Deliverable:

```text
Worker

↓

Register

↓

Online

↓

Heartbeat

↓

Idle

↓

Lease

↓

Busy

↓

Heartbeat Timeout

↓

Offline

↓

Reconnect
```

This becomes one of the core architecture docs.

---

# Epic 2 – Maintenance Framework ⭐⭐⭐⭐⭐

Instead of implementing cleanup everywhere...

Build a proper maintenance subsystem.

Example

```text
MaintenanceService

↓

LeaseCleanup

↓

WorkerCleanup

↓

AssignmentCleanup

↓

MetricsCleanup
```

Now future cleanup logic plugs in cleanly.

---

# Epic 3 – Lease Lifecycle ⭐⭐⭐⭐⭐

I think leases deserve a full review.

Questions I'd answer:

* Can leases be revoked?
* Can they expire?
* Can they be renewed?
* Can they be recovered?
* Are they auditable?
* Can they be replayed?

I'd probably add

```text
Lease State Machine
```

instead of just ACTIVE/DELETE.

---

# Epic 4 – Event System ⭐⭐⭐⭐☆

You already have EventLog.

Expand it.

Examples

```text
WorkerRegistered

WorkerHeartbeat

WorkerOffline

LeaseCreated

LeaseExpired

LeaseRevoked

AssignmentStarted

AssignmentCompleted

AssignmentFailed
```

Then document:

* event taxonomy
* severity
* retention
* correlation IDs

---

# Epic 5 – Service Layer Refactor ⭐⭐⭐⭐⭐

This is the one I think is most important technically.

Current

```text
routers/

↓

business logic
```

Target

```text
routers/

↓

services/

↓

repositories/

↓

database
```

Future features become dramatically easier.

---

# Epic 6 – Knowledge System Validation ⭐⭐⭐⭐☆

Not redesign.

Validation.

Every completed story should answer:

* Did bootstrap work?
* Which docs were used?
* Which docs weren't?
* What was missing?
* Was documentation updated appropriately?

Collect evidence.

Don't redesign.

---

# Epic 7 – Architecture Cleanup ⭐⭐⭐⭐☆

Now that you have the knowledge system...

Start converting

```text
Infrastructure docs
```

into

```text
Domain docs
```

Examples

```
Worker

Lease

Assignment

Scheduler

Execution

Browser
```

instead of

```
Database

Network

Models
```

This is evolutionary, not a rewrite.

---

# Things I would deliberately NOT build

I'd postpone:

* Proxy management UI
* Browser profile marketplace
* Advanced dashboards
* WebSockets
* Multi-region scheduling
* Billing enhancements
* Tenant analytics

Those are valuable, but they'll benefit from a stronger foundation.

---

# Sprint 10 Success Criteria

At the end of Sprint 10, I'd want to be able to say:

* Workers recover automatically from crashes.
* Leases are fully auditable.
* Maintenance logic is centralized.
* Business logic has begun moving out of routers.
* Event taxonomy is consistent.
* AI bootstrap works reliably across multiple fresh chats.
* The Knowledge Manager updates only what's necessary.
* No documentation bloat occurred.

Notice that only one of those is user-visible. That's okay. This sprint is about making the platform easier to extend.

---

# What I'd call Sprint 11

Once Sprint 10 hardens the platform, Sprint 11 becomes much more exciting:

> **"Execution Intelligence & Scheduler Evolution"**

That's where I'd look at:

* Smarter scheduling (capability-aware, load-aware, priority-aware).
* Retry policies.
* Execution telemetry.
* Failure classification.
* Worker selection strategies.
* Cross-project orchestration.

Those features will build on a cleaner worker lifecycle and maintenance model rather than fighting against them.

