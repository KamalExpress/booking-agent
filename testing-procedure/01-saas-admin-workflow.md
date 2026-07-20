
# SaaS Admin (Super Admin) Testing Workflow

## Objective

Verify that the SaaS Admin can effectively monitor global system health, manage tenant lifecycle, and oversee the execution plane (Headless Workers) without interfering with tenant-isolated data.

## Prerequisites

* **0.1.** Log in to the Cloud SaaS portal as a user with `role = SUPER_ADMIN`. **[Passed]**
* **0.2.** Ensure at least one Scraper worker and one Booker worker are online and polling the SaaS. **[Failed]**

## Test Cases

### 1. Global Dashboard & Auto-Scaling

* **1.1.** **Action:** Navigate to the main dashboard (`/`).
* **1.1.1. Expected Result:** The **Auto-Scaling Dial (Capacity Ratio)** correctly calculates `(Idle Workers / Pending BookingTasks) * 100`.
* **1.1.2. Expected Result:** **System Health Score** correctly reflects recent `SLOT_FOUND` events and active worker heartbeats.
* **1.1.3. Expected Result:** The **Global Assignment Map** displays active, deduplicated scraping assignments currently leased to workers.



### 2. Tenant Management

* **2.1.** **Action:** Navigate to the Tenants list (`/tenants`).
* **2.1.1. Expected Result:** Ability to view all tenants.


* **2.2.** **Action:** Create a new Tenant.
* **2.2.1. Expected Result:** Form requires a Tenant Name, Admin Email, and Admin Password.
* **2.2.2. Expected Result:** Upon submission, the Tenant and its root Tenant Admin user are created.


* **2.3.** **Action:** Suspend a Tenant.
* **2.3.1. Expected Result:** Suspending a tenant instantly deactivates all staff/users belonging to that tenant, cutting off their UI access.
* **2.3.2. Expected Result:** The "Default Tenant" with ID=1 is protected from suspension.



### 3. Execution Plane Monitoring

* **3.1.** **Action:** Navigate to the Worker Fleet / Diagnostics page.
* **3.1.1. Expected Result:** Active workers are listed with their capabilities (`can_scrape`, `can_book`).
* **3.1.2. Expected Result:** The `last_heartbeat` and `scheduling_state` (e.g., "Accepting Jobs") are accurately reflected.



### 4. Global Configuration (System Settings)

* **4.1.** **Action:** Navigate to Settings.
* **4.1.1. Expected Result:** Admin can update global properties (e.g., `global.visa_centers_config` or CapSolver API keys).
* **4.1.2. Expected Result:** Verification that updating the config triggers a `SaaS requested runtime config refresh` log in the worker nodes on their next heartbeat.