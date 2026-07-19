# Implementation Plan: Level 1 - Database Foundation & Models

## Objective
Establish the foundational data structures required for proactive Applicant Waitlisting, OTP tracking, and strict Tenant isolation for the execution plane assets.

## Proposed Changes
### `ttttt/cloud-saas/app/models.py`
1. **New Model: `Applicant`**
   - **Fields:** `id`, `tenant_id` (FK), `surname`, `firstname`, `dateofbirth`, `gender`, `nationality`, `passportnumber`, `passport_expiry`, `email`, `phone_prefix`, `phone_number`.
   - **JSONB Extensibility:** Add `provider_metadata` (JSONB) to store any future portal-specific requirements (e.g., VFS GWF numbers) without altering the schema.
   - **Relationships:** Belongs to a `Tenant`. Has many `WaitlistQueue` entries.

2. **New Model: `WaitlistQueue`**
   - **Fields:** `id`, `tenant_id` (FK), `applicant_id` (FK), `provider` (e.g., 'GVC'), `visa_center` (e.g., '138' for Lahore), `appointment_type` (e.g., '0' for Short Term).
   - **State:** `status` (PENDING, BOOKED, CANCELLED), `priority` (Integer, default 0).
   - **Relationships:** Belongs to an `Applicant`. 

3. **Modifications: `BookingTask`**
   - **New Fields:** `otp_code` (String, nullable).
   - **Update Foreign Keys:** Add `applicant_id` (FK, nullable) to explicitly link the task back to the queued applicant.

4. **Modifications: `PortalAccount` & `Proxy`**
   - **New Fields:** `tenant_id` (Integer, ForeignKey to `tenants.id`, nullable for globally shared assets, but strictly set for Tenant-owned assets).
   - **Schema Update:** Ensure deletion cascades appropriately or sets to NULL.

5. **New Model: `InboxMessage` (Preparation for Level 4)**
   - **Fields:** `id`, `tenant_id` (FK), `severity` (info, warning, error, success), `title`, `body`, `is_read` (Boolean, default False), `created_at`.

## Verification Plan
- Generate alembic migration script (`alembic revision --autogenerate -m "level_1_foundation"`).
- Since we are not running migrations locally per `AGENTS.md`, we will inspect the generated alembic script for correctness.
- Write a quick Python test script in `ttttt/cloud-saas/` that imports `models.py`, initializes an in-memory SQLite DB (or uses the local Postgres), and attempts to create an `Applicant` and queue them in the `WaitlistQueue` to verify relationships work seamlessly.
