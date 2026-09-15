# ADR-006: Tenant Wallet Balance and Per-Booking Pricing / Credit Control

## Status
Approved for Future Implementation (Sprint Backlog)

## Context
The SaaS platform operates as a multi-tenant B2B solution where agencies (Tenants) submit applicants to the waitlist queue for automated slot booking. To monetize the service and protect infrastructure compute resources, the SaaS Admin (platform owner) needs platform-level control over per-booking service pricing and tenant credit balances.

### Key Requirements
1. **Configurable Unit Price:** The SaaS Admin can configure a global or tenant-specific price per booking (e.g., .00 USD or equivalent currency per booking task).
2. **Prepaid Tenant Wallet / Balance:** Each tenant maintains a ledger balance (wallet_balance).
3. **Enqueue & Dispatch Balance Enforcement:**
   - When a tenant adds N applicants to the queue (e.g., 10 applicants at .00/booking), the system verifies that the tenant has at least .00 in their wallet.
   - A two-phase reservation model: reserve credit when an applicant is enqueued/dispatched into a BookingTask, and finalize deduction upon BOOKING_SUCCESS. If the booking fails or expires, the reserved credit is returned to the tenant's available balance.
4. **Platform Control:** Prevents tenants with insufficient funds from monopolizing scheduler compute capacity and bot booking swarms.

## Decision
We will implement a **Tenant Prepaid Wallet & Reservation Ledger** in an upcoming sprint:

1. **Database Schema Enhancements:**
   - Tenant.wallet_balance: Float / Decimal representing current liquid credit balance.
   - Tenant.price_per_booking: Float / Decimal allowing custom tiered rates per tenant (falling back to a global default in SystemSetting).
   - WalletTransaction: An immutable ledger of all deposits, reservations, deductions, and refunds (id, 	enant_id, mount, 	ransaction_type, eference_task_id, created_at).
2. **Enqueue Guardrail:**
   - In /queue/add and /api/v1/queue, verify vailable_balance >= price_per_booking before allowing staff/admin to enqueue applicants.
3. **Execution-Time Settlement:**
   - On BOOKING_DISPATCHED, place a hold/reservation on the required amount.
   - On BOOKING_SUCCESS, capture the reservation as a completed deduction.
   - On BOOKING_FAILED / EXPIRED, release the hold back to the tenant's balance.

## Consequences
- **Positive:** Gives SaaS Admins direct commercial control over platform usage and prevents abuse of compute/captcha resources.
- **Positive:** Clear audit trail of financial and booking transactions per tenant.
- **Negative:** Requires handling edge cases like concurrent enqueues and credit race conditions using database row locks (with_for_update).

## Related Components
- cloud-saas/app/models.py (Tenant, WalletTransaction, BookingTask)
- cloud-saas/app/services/scheduler_service.py (Credit check during auto-dispatch)
- cloud-saas/app/routers/ui.py (Wallet top-up, ledger view, and price configuration)

---
*Last Reviewed: Current Sprint | Implementation Verified: PLANNED | Owner: Knowledge Manager | Confidence: High*
