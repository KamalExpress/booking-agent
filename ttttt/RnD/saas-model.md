# Multi-Tenant SaaS Architecture

Transforming the "Kamal Express Appointment Monitor" from an internal tool into a B2B SaaS (Software as a Service) platform is highly feasible and incredibly lucrative. This model allows you to sell the notification service to other travel agencies or visa consultancies on a monthly subscription.

This document outlines the architecture, security, and scaling required for this transition.

## 1. The Multi-Tenant Architecture

Instead of running a separate server for every agency, you run **one central backend** that serves multiple "Tenants". 

### Centralized Scraping (The "Fan-Out" Model)
**Crucial Advantage:** If 50 different agencies are all monitoring the GVC portal for the same appointment types, you **do not** want 50 different bots scraping the portal simultaneously. This will instantly trigger Cloudflare IP bans.
- Instead, the **Super Admin System** runs a single, highly optimized bot that checks the portal every 5 minutes.
- When an open slot is found, the backend executes a "Fan-Out" operation, blasting push notifications simultaneously to the staff of **all subscribed and active Tenants**.

## 2. Roles and Permissions

To prevent abuse, sharing, and under-the-table dealing, the system requires strict Role-Based Access Control (RBAC).

| Role | Capabilities |
| :--- | :--- |
| **Super Admin** | You (System Owners). Full access to create/suspend Tenants, view global audit logs, manage the core scraping bot, and configure global Captcha APIs. |
| **Tenant Admin** | e.g., Kamal Express Manager. Can add/remove their own staff members, view tenant-specific audit logs, and manage their subscription/billing. |
| **Staff / Clerk** | Can log into the PWA, view the dashboard, and receive push notifications. **Cannot** add users or change core system settings. |

## 3. Security & Anti-Abuse Measures

To prevent a clerk from sharing their login credentials with third parties or charging under-the-table fees:

1. **Strict Audit Logging:** Every action is recorded in a database.
   - *Example Log:* `[2026-07-09 14:00] User 'ali_clerk' (Tenant: KamalExpress) logged in from IP 192.168.1.5 on an iPhone.`
   - This allows Tenant Admins to monitor who is logging in and from where.
2. **Concurrent Session Limits:** A staff account can only be logged in on **one device at a time**. If they share their password with a third party, logging in on the new device immediately kicks out the original staff member, deterring sharing.
3. **MFA / Device Binding:** Push notifications are tied to a specific physical device (via Web Push VAPID keys). A user cannot just copy a link; they must be logged into the PWA to receive the alerts.

## 4. Technical Implementation Changes

Moving to a SaaS model requires upgrading our data layer:

- **Database Transition:** We must replace `config_manager.py` (which uses flat JSON files) with a robust relational database like **PostgreSQL**.
- **Authentication:** We will implement **JWT (JSON Web Tokens)** in FastAPI for secure, stateless user logins.
- **Data Isolation:** Every database table (`users`, `settings`, `logs`) will have a `tenant_id` column. The FastAPI backend will strictly filter queries so Tenant A can never see Tenant B's data.
- **The "Seed" Phase:** We will create a database seeding script that automatically creates the "Super Admin" account and the default "Kamal Express" tenant with your staff accounts upon initial deployment.

## Conclusion
Pivoting to a SaaS model is the smartest long-term strategy. It centralizes the bot's workload, prevents Cloudflare bans, and turns an internal utility into a revenue-generating product. We can easily implement this RBAC system inside the FastAPI backend we are about to build.
