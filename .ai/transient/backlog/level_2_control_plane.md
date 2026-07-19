# Implementation Plan: Level 2 - Control Plane (Scheduler Engine)

## Objective
Upgrade the SaaS Scheduler to automatically route `SLOT_FOUND` events to the new Waitlist Queue, enforce Tenant asset isolation, and implement the OTP relay webhook with race-condition prevention.

## Proposed Changes
### 1. Webhook API (`ttttt/cloud-saas/app/routers/webhooks.py`)
- **New Endpoint:** `POST /api/webhooks/otp`
  - Accepts payload from `android_income_sms_gateway_webhook` (Sender, Text, Device ID).
  - Uses Regex to extract the 6-digit GVC OTP.
  - Looks up the active `BookingTask` matching the recipient phone number (or tenant mapping) and updates `BookingTask.otp_code`.

### 2. Scheduler Engine (`ttttt/cloud-saas/app/services/scheduler_service.py` & `lease_service.py`)
- **Event Handling:** When `SLOT_FOUND` is received, instead of broadcasting passively, trigger `auto_dispatch_queue(visa_center)`.
- **Parallel Queue Dispatch:** 
  - Query `WaitlistQueue` ordered by `priority`, filtered by `visa_center` and `status='PENDING'`.
  - Use `SELECT FOR UPDATE SKIP LOCKED` to atomically claim $N$ applicants matching the number of open slots.
  - Generate a `BookingTask` for each claimed applicant, moving their Queue status to `BOOKED` (or `IN_PROGRESS`).
- **OTP Locking Mechanism:** 
  - Before creating the `BookingTask`, check if the applicant's phone number is already actively locked by a running `BookingTask`. If yes, skip to the next applicant to avoid the OTP race condition, maximizing success rates.
- **Tenant Isolation Policy (`scoring_policy.py`):** 
  - Ensure that when a Booker worker requests a Lease for a `BookingTask` owned by Tenant X, the scheduler strictly filters `PortalAccount` and `Proxy` candidates where `tenant_id == X` (or `tenant_id IS NULL` for shared global assets).

## Verification Plan
- Write integration tests using Pytest in `ttttt/cloud-saas/tests/`:
  - Simulate a `SLOT_FOUND` event with 3 slots and ensure exactly 3 `BookingTasks` are created.
  - Send a mock HTTP POST to `/api/webhooks/otp` and verify the `BookingTask.otp_code` is updated correctly.
