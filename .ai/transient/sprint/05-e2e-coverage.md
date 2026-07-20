# End-to-End Test Coverage Matrix

**Last Run Date/Time:** 2026-07-20T16:05:00+05:00
**Environment:** Staging (`feature/staging` branch)
**Status:** **PASSED** (All implemented tests are green)

This document tracks the coverage of our Playwright testing suite against the standardized workflow definitions found in `.ai/transient/testing-procedure/`.

---

## 1. SaaS Admin (Super Admin) Workflow
**Spec File:** `01-saas-admin.spec.js`

| ID | Test Description | Status | Implemented? |
| :--- | :--- | :---: | :---: |
| 0.1 | Log in as SUPER_ADMIN | ✅ Passed | Yes |
| 1.1.1 | Auto-Scaling Dial logic & visibility | ✅ Passed | Yes |
| 1.1.2 | System Health Score reflects heartbeats | ✅ Passed | Yes |
| 1.1.3 | Global Assignment Map visibility | ✅ Passed | Yes |
| 2.1.1 | View all isolated tenants | ✅ Passed | Yes |
| 2.2.2 | Create new Tenant (Dynamic State Generation) | ✅ Passed | Yes |
| 2.3.2 | Default Tenant (ID=1) protected from suspension | ✅ Passed | Yes |
| 3.1 | Execution Plane Monitoring (Worker Fleet Status) | ❌ Missing | No |
| 4.1 | Global Configuration (Updating API Keys) | ❌ Missing | No |

---

## 2. Tenant Admin Workflow
**Spec File:** `02-tenant-admin.spec.js`

| ID | Test Description | Status | Implemented? |
| :--- | :--- | :---: | :---: |
| 0.1 | Log in as TENANT_ADMIN | ✅ Passed | Yes |
| 1.1.1 | PWA Dashboard isolated metrics visibility | ✅ Passed | Yes |
| 1.1.2 | Asset Burn Dashboard (Accounts & Proxies Health) | ✅ Passed | Yes |
| 2.4.1 | Ensure Tenant Admin cannot grant SUPER_ADMIN | ✅ Passed | Yes |
| 3.1 | SMS/Phone Webhook Configuration (`Tenant.phone_number`) | ❌ Missing | No |
| 4.1 | Tenant Inbox (Localized Notifications Check) | ❌ Missing | No |

---

## 3. Tenant Staff (Travel Agent) Workflow
**Spec File:** `03-tenant-staff.spec.js`

| ID | Test Description | Status | Implemented? |
| :--- | :--- | :---: | :---: |
| 0.1 | Log in as TENANT_STAFF | ✅ Passed | Yes |
| 1.2 | Client Directory: Full Applicant Creation Flow | ✅ Passed | Yes |
| 2.2 | Waitlist Queue: Form Submission and `PENDING` status | ✅ Passed | Yes |
| 3.1 | Automated Dispatch (Scraper trigger -> Queue Pop) | ❌ Missing | No* |
| 3.2 | OTP Consumption (Android Gateway Webhook -> Booking) | ❌ Missing | No* |

*\*Note on Missing Tests for Section 3:*
*The missing tests in Section 3 evaluate the background headless worker plane and external Android Webhook inputs. Playwright is primarily a frontend browser automation tool. To fully E2E test this section automatically, we would need to mock the `POST /api/webhooks/otp` endpoints or create API-level integration tests in Python (`pytest`) rather than Playwright.*
