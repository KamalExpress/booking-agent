# Architectural Specification: Subscription Tiers, Notification Monetization & Feature Gating

## 1. Executive Summary & Monetization Strategy
The platform utilizes a **Hybrid Monetization Model**:
1. **Recurring Monthly Subscription (Base Access):** Unlocks real-time slot drop push notifications, multi-center monitoring, staff seats, and queue capacity.
2. **Usage-Based Wallet (Per-Booking Success Fee):** Prepaid credit balance used to automatically execute and claim visa appointment bookings when slots are detected.

---

## 2. Subscription Tiers Comparison Matrix

| Feature / Dimension | Free (Community / Trial) | Starter | Pro (Recommended) | Agency / Enterprise |
| :--- | :--- | :--- | :--- | :--- |
| **Target Audience** | Evaluation / Freelance Agents | Small Boutiques (1-3 staff) | Established Consultancies | High-Volume Agency Networks |
| **Monthly Base Price** | ** / month** | ** / month** | ** / month** | ** / month** |
| **Per-Booking Fee** | .50 / booking | .50 / booking | .00 / booking | .75 / booking |
| **Slot Alert Speed** | Delayed (5-10 min digest) | Real-Time (Instant 0s) | Real-Time (Instant 0s) | Real-Time (Instant 0s + Dedicated) |
| **Notification Channels**| WebPush (1 Device) | WebPush (Up to 3 Devices) | WebPush + Telegram Bot | WebPush + Telegram + WhatsApp/SMS |
| **Marketing Hook Ticker**| Active (Public Bookings Feed)| Disabled | Disabled | Disabled |
| **Monitored Centers** | 1 Center (e.g. Islamabad) | Up to 3 Centers | All GVC Centers (Unlimited) | All Centers + Custom Priorities |
| **Staff Member Seats** | 1 (Admin only) | 3 Staff Accounts | 10 Staff Accounts | Unlimited Staff Accounts |
| **Waitlist Queue Size** | Max 2 Applicants | Max 15 Applicants | Max 100 Applicants | Unlimited Applicants |
| **Auto-Booker Engine** | Disabled (Manual only) | Standard Priority | High Priority | VIP Front-of-Line Priority |
| **Dedicated Proxy Pool**| Shared General Pool | Shared General Pool | High-Reputation Pool | Dedicated Isolated Subnet |

---

## 3. UI/UX Changes & Gating Mechanisms

### 3.1 Free Tier Experience & Growth Loops
- **Marketing Feed / Live Ticker:** Displays real-time anonymous booking activity to drive FOMO:
  "⚡ Booking confirmed for Ali (Passport: PK***892) via Kamal Express. Upgrade to Pro for instant 0-second auto-booking."
- **Quota Meters:**
  - Queue Management page shows visual usage bars (e.g., Queue: 2/2 used).
  - Attempting to add a 3rd applicant triggers a sleek **"Upgrade to Starter / Pro"** modal.
- **Feature Badges:** Advanced options (e.g., Telegram Bot Webhook, Type D Seasonal Category, VIP Priority) display a shiny PRO or AGENCY pill with click-to-upgrade actions.

### 3.2 Tenant Billing & Wallet Dashboard (/billing)
- **Plan Management Card:** Displays Active Plan, Next Billing Cycle, and 1-click Upgrade / Downgrade options.
- **Prepaid Wallet Widget:** Real-time balance display ($ USD / PKR) with quick Top-Up buttons (, , ) integrating Stripe / local gateways.
- **Usage & Ledger Breakdown:**
  - Notification Deliveries count (Current Month).
  - Completed Booking Deductions vs. Refunded Attempts.

### 3.3 Super Admin Platform Controls (/tenants/{id}/billing)
- Ability for Platform Super Admins to:
  - Override a tenant's subscription plan (e.g., extend trial, grant Pro for VIP agency).
  - Set custom price-per-booking rates for individual tenants.
  - Set minimum wallet balance requirements for queue dispatch.
  - Enable/disable specific notification channels per tenant.

---
*Status: Approved for Sprint Backlog | Owner: Product & Architecture Team*
