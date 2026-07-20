
# Tenant Staff (Travel Agent) Testing Workflow

## Objective

Verify that a Travel Agent can seamlessly onboard new applicants into the database and push them into the automated `WaitlistQueue` for a specific Visa Center.

## Prerequisites

* **0.1.** Log in to the Cloud SaaS portal as a user with `role = TENANT_STAFF`.
* **0.2.** Ensure the Tenant's proxy, account, and phone number are properly configured by the Tenant Admin.

## Test Cases

### 1. Client Directory (Applicant Creation)

* **1.1.** **Action:** Navigate to the Clients / Applicants page.
* **1.2.** **Action:** Click "Add Applicant".
* **1.2.1. Action:** Fill out the standardized form (First Name, Surname, DOB, Passport Number, Passport Expiry, Nationality, Phone Number, Email).
* **1.2.2. Expected Result:** Upon submission, the `Applicant` record is saved to the database, explicitly tied to the staff member's `tenant_id`.
* **1.2.3. Expected Result:** Ensure the user cannot view or edit applicants belonging to other Tenants.



### 2. Pushing to the Waitlist

* **2.1.** **Action:** Navigate to the Queue Management / Waitlist page.
* **2.2.** **Action:** Select an existing Applicant and add them to the `WaitlistQueue`.
* **2.2.1. Expected Result:** Form requires selecting the Target Visa Center (e.g., 138 for Lahore) and Appointment Type (e.g., 26).
* **2.2.2. Expected Result:** Upon submission, the Applicant appears in the Waitlist table with a `PENDING` status.



### 3. Automated Dispatch & OTP Consumption (End-to-End Simulation)

* **3.1.** **Action:** Observe the Waitlist while the system runs in the background *(Requires Scraper & Booker running)*.
* **3.1.1. Expected Result:** When a Scraper worker finds slots, the Scheduler should automatically pop the Applicant from the `WaitlistQueue`.
* **3.1.2. Expected Result:** The Waitlist status should transition from `PENDING` to `IN_PROGRESS` (or disappear into the Active Booking Tasks view).
* **3.1.3. Expected Result:** The Booker worker picks up the task and triggers an SMS OTP.


* **3.2.** **Action:** Trigger the Android SMS Gateway Webhook manually (or let the app do it) with the GVC code.
* **3.2.1. Expected Result:** Verify the `BookingTask.otp_code` is updated in the database.
* **3.2.2. Expected Result:** The Booker worker consumes the OTP, finalizes the appointment, and the Applicant's final status becomes `BOOKED`.