# Implementation Plan: Level 4 - UI & UX (Dashboards)

## Objective
Build the front-end interfaces required for Travel Agents to manage applicants, Tenant Admins to monitor resources, and SaaS Admins to oversee the global worker fleet.

## Proposed Changes
### `ttttt/cloud-saas/app/routers/ui.py` & Templates
1. **Travel Agent UI (`templates/staff.html` or new `queue.html`)**
   - **Client Directory Form:** A dynamic form (rendered based on GVC requirements) to add new `Applicant`s.
   - **Queue Management:** A table showing the `WaitlistQueue`. Travel Agents can add an applicant to the queue for a specific `visa_center`.

2. **Tenant Admin UI (`templates/tenant_detail.html`)**
   - **Asset Burn Dashboard:** Visual indicators (e.g., progress bars) showing the health ratio of their `PortalAccount`s and `Proxy` IPs.
   - **Phone Configuration:** A simple CRUD interface allowing them to register their physical phone numbers (used by the Android Webhook) so the SaaS knows which OTPs belong to their agency.
   - **SaaS Inbox:** A notification dropdown or dedicated page pulling from the `InboxMessage` table, displaying successful booking alerts and resource threshold warnings.

3. **SaaS Admin UI (`templates/dashboard.html`)**
   - **Auto-Scaling Dial:** A live widget displaying the `Worker Capacity Ratio` (`(Idle + Accepting Jobs) / Pending BookingTasks`). This instructs the Admin when to scale Docker containers.
   - **Global Assignment Map:** A unified table showing deduplicated, active global scraping operations, highlighting which Scraper worker is currently assigned to which Visa Center.
   - **Centralized Settings:** A secure UI table to manage `SystemSettings` (e.g., updating the global CapSolver API key).

## Verification Plan
- Launch the FastAPI UI application locally.
- Log in as a `STAFF` user and verify the Applicant Form saves data to the DB.
- Log in as a `TENANT_ADMIN` and verify the Phone Configuration screen.
- Log in as a `SUPER_ADMIN` and verify the Auto-Scaling Dial calculates metrics correctly.
