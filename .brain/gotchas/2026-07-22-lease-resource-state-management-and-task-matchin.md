---
type: "gotcha"
title: "Lease Resource State Management and Task Matching"
summary: "Leases must reset associated `PortalAccount` and `Proxy` statuses back to `\"READY\"` upon completion, failure, cancellation, or expiration."
tags:
  - "ali raza"
  - "antigravity"
  - "gemini"
  - "gotcha"
  - "ide"
  - "users"
importance: "medium"
score: 60
hit_count: 0
last_used: null
created_at: "2026-07-22T09:02:01.548Z"
created: "2026-07-22"
updated: "2026-07-22"
stale: false
supersedes: null
superseded_by: null
version: 1
date: "2026-07-22"
source: "manual"
status: "active"
related: []
path_scope: []
files: []
recommended_skills: []
required_skills: []
suppressed_skills: []
skill_trigger_paths: []
skill_trigger_tasks: []
valid_from: "2026-07-22"
observed_at: "2026-07-22T09:02:01.548Z"
review_state: "cleared"
invocation_mode: "optional"
risk_level: "low"
---

- Leases must reset associated `PortalAccount` and `Proxy` statuses back to `"READY"` upon completion, failure, cancellation, or expiration.
- Booking task completions and failures are reported by workers using the booking task ID as the `assignment_id` argument. Therefore, lease lookups inside `complete_lease` and `fail_lease` must match on either `assignment_id` or `booking_task_id`.
- If a worker goes offline (e.g., heartbeat timeout), its active leases must be abandoned immediately (`abandon_worker_leases`) to free locked accounts and proxies instead of waiting for individual TTL timeouts.
