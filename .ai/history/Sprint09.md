# Architecture Timeline: Sprint 09

## Architecture Changes
- Initiated the formal separation of the Cloud SaaS (Control Plane) and the Desktop Workers (Execution Plane).
- Integrated `sqladmin` directly into the FastAPI application, deprecating external DB viewer tools for Super Admins.
- Implemented Web Push notifications natively in the SaaS utilizing VAPID keys.

## Added
- Push Notification History table tracking successful and failed delivery counts per tenant.
- Slot Availability details UI showing specific 15-minute intervals.
- The `.ai/` Knowledge Base and `.agents/` Role configurations.

## Removed / Deprecated
- The concept of the SaaS directly querying Visa portals was fully deprecated. All automation now flows strictly through the headless workers.

## Future Work
- Implementation of robust appointment types (`0`, `2`, `6`, `26`) in Assignment creation.
- A background task to prune stale push notification subscriptions.
- Event sourcing telemetry for billing metrics (bandwidth, captchas).

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
