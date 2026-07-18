# Sprint 09: Current State & Handoff

## Current Sprint
Sprint 10 (Completed) / Transitioning to Sprint 11

## Completed Work
- **Dual Worker Pools**: Decoupled scrapers and bookers.
- **Proxy Management**: Added robust proxy tracking, capabilities, and health scoring.
- **Scheduler Brain**: Created `SchedulerService` and `ScoringPolicy` to intelligently lease resources based on health and timeouts.
- **Explain, Diagnose & Recover (EDR)**: Implemented `OperationalGuidance` web component and comprehensive event mapping in `guidance.py`.
- **UI Enhancements**: Refactored Accounts, Proxies, Diagnostics, and Booking Tasks dashboards.

## In-Progress Work
- None. Clean transition state.

## Blockers
- None.

## Next Priorities (Sprint 11)
- **Stale Notification Cleanup:** Implement a background task or manual SaaS admin trigger to clean up expired/dead Web Push subscriptions from the `PushSubscription` table to prevent sending pushes to dead devices.
- **Worker Management UI:** Further refine dashboard pages to visualize worker health (Heartbeats, Scheduling State, Current Assignments).

## Important Implementation Notes
- Billing metrics (Captcha success rates, Proxy bandwidth tracking) were analyzed and formally planned (see `.ai/permanent/adr/005-billing-metrics.md`) but deferred to keep workers lightweight.
- Ensure any new UI routes are protected by the `get_ui_user` dependency and appropriate role checks.

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
