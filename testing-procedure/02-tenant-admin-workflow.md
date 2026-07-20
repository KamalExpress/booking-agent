
# Tenant Admin Testing Workflow

## Objective

Verify that the Tenant Admin can successfully manage their agency's isolated assets (accounts, proxies, phone numbers), monitor burn rates, and manage their staff members.

## Prerequisites

* **0.1.** Log in to the Cloud SaaS portal as a user with `role = TENANT_ADMIN`.

## Test Cases

### 1. Asset Burn Dashboard

* **1.1.** **Action:** Navigate to the Tenant Dashboard (`/`).
* **1.1.1. Expected Result:** The UI strictly displays metrics only for this specific Tenant.
* **1.1.2. Expected Result:** The **Asset Burn Indicators** (Progress bars) accurately display:
* `Good Accounts / Total Accounts`
* `Good Proxies / Total Proxies`


* **1.1.3. Expected Result:** Any accounts or proxies in `DISABLED` or `Error` state should lower the health ratio.



### 2. Staff Management

* **2.1.** **Action:** Navigate to the Staff/Users section.
* **2.1.1. Expected Result:** Admin can only see users belonging to their `tenant_id`.


* **2.2.** **Action:** Create a new user with `role = TENANT_STAFF`.
* **2.3.** **Action:** Edit an existing user (change password or deactivate).
* **2.4.** **Action:** Attempt to assign `SUPER_ADMIN` privileges during user creation or edit.
* **2.4.1. Expected Result:** Ensure a Tenant Admin cannot grant `SUPER_ADMIN` privileges.



### 3. SMS/Phone Configuration for Webhooks

* **3.1.** **Action:** Navigate to the Settings/Configuration page.
* **3.1.1. Expected Result:** Admin can input and save the physical Phone Number attached to their Android SMS Gateway device.
* **3.1.2. Expected Result:** Verify that this phone number is saved to `Tenant.phone_number` in the database.
* **3.1.3. Expected Result:** *(Crucial for Level 2 Control Plane: This number is used to map incoming webhook OTPs back to this specific Tenant's booking tasks).*



### 4. Tenant Inbox

* **4.1.** **Action:** Check the Notifications / Inbox panel.
* **4.1.1. Expected Result:** Displays messages from the `InboxMessage` table filtered by this `tenant_id`.
* **4.1.2. Expected Result:** Should show localized alerts (e.g., "Account banned", "Booking Successful for Applicant X").