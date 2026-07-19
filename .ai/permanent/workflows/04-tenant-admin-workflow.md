# Tenant Admin Workflow & Gap Analysis

This report outlines the platform workflow from the perspective of a **Tenant Admin** (e.g., the owner or manager of a Travel Agency). Unlike standard Staff (Travel Agents) who focus on adding applicants and tracking bookings, the Tenant Admin focuses on resource provisioning, team management, and operational health.

---

## 1. The Tenant Admin Workflow

### Phase A: Agency Setup & Provisioning
1. **Staff Management:** The Admin logs into the SaaS and invites their Travel Agents (`RoleEnum.STAFF`) to the platform, managing their access.
2. **Resource Injection:** The Admin provisions the raw materials required for the Execution Plane:
   - **Portal Accounts:** They bulk-upload GVC credentials (`PortalAccount`).
   - **Proxies & Captcha (Business Opportunity):** They add dedicated IP proxies and configure Captcha solving parameters. 
     *Note on SaaS Monetization:* The SaaS can optionally provide high-quality proxies and centralized CapSolver quotas directly to the Tenants. The SaaS could bill the Tenant at standard market price plus a margin. This creates an additional revenue stream while simplifying onboarding for the Tenant.
3. **OTP Pipeline Configuration:** The Admin configures the SMS gateway app on the agency's physical phone(s) and maps the phone numbers to their respective GVC accounts in the SaaS dashboard, ensuring the Booker workers know where to fetch OTPs.

### Phase B: Operational Monitoring
4. **Resource Burn Tracking:** The Admin monitors the "Asset Health" dashboard. They track how many proxies have been temporarily banned by WAFs or how many GVC accounts are in a cooldown state due to daily rate limits. 
5. **Success Analytics:** They view agency-wide reporting to see the success rate (Total Waitlisted vs. Total Booked) and identify if they need to provision more resources.

---

## 2. Gaps & Pending Items for Tenant Admins

To provide a fully autonomous management experience for Tenant Admins, the following gaps in the Control Plane must be addressed:

### Gap 1: Asset Isolation & Resource Pools
* **The Issue:** Are proxies and GVC accounts shared globally, or isolated per Tenant? 
* **The Solution:** They must be strictly **Tenant-Isolated**. If Tenant A uses low-quality proxies and triggers aggressive WAF rules on a GVC account, it must not affect Tenant B. The Scheduler must only bind a `BookingTask` to a `PortalAccount` and `Proxy` owned by that specific `tenant_id`.
* **Pending Task:** Enforce `tenant_id` foreign keys on the `Proxy` and `PortalAccount` models, and update the Scheduler's `ScoringPolicy` to respect tenant boundaries during resource leasing.

### Gap 2: OTP Webhook Mapping UI
* **The Issue:** The OTP relay pipeline relies on an Android app sending SMS data to the SaaS webhook. The SaaS needs to know *which* agency the SMS belongs to.
* **The Solution:** The Tenant Admin UI needs a "Phone Numbers" settings page. The Admin registers their physical phone numbers here. When the global `/api/webhooks/otp` receives a payload, it matches the recipient phone number to the Tenant, and then to the active `BookingTask`.
* **Pending Task:** Create a `TenantPhoneNumber` mapping table and the corresponding UI management screens.

### Gap 3: Automated Resource Alerts
* **The Issue:** The Tenant Admin shouldn't have to manually check if they have run out of healthy proxies.
* **The Solution:** Implement system-generated Push/Inbox notifications alerting the Tenant Admin when their healthy asset pool drops below a critical threshold (e.g., *"Warning: 80% of your Proxies are currently in Cooldown. Please add more proxies to ensure bookings do not fail."*).
* **Pending Task:** Create a background cron job in the SaaS that calculates Tenant asset health and dispatches threshold alerts.
