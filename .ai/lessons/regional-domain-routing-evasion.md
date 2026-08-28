# Cross-Regional Domain Routing & Load Shedding Strategy

## 1. Observation & Ground Truth
During peak slot opening windows in Pakistan, a live test revealed:
- A developer authenticated and secured a visa appointment smoothly via the Bangladesh regional endpoint (\d-gr-services.gvcworld.eu\) without experiencing any origin server load, 502/503 timeouts, or aggressive Imperva WAF blocks.
- Concurrently, direct requests against \pk-gr-services.gvcworld.eu\ suffered from extreme connection queuing, aggressive Imperva \_Incapsula_Resource\ challenges, and intermittent downtime.

## 2. Technical Root Cause & Architecture Insights
1. **Shared Infrastructure & Centralized Auth:**
   - GVC's regional subdomains (\pk-gr-services.gvcworld.eu\, \d-gr-services.gvcworld.eu\, \in-gr-services.gvcworld.eu\) communicate with a shared backend database and centralized authentication system.
   - User credentials registered on one regional portal are valid across related subdomains.
2. **Independent WAF Anomaly Profiles:**
   - Imperva and origin rate limiters maintain separate dynamic risk profiles and anomaly counters per FQDN (Fully Qualified Domain Name).
   - When thousands of applicants and bots flood \pk-gr-services\, Imperva shifts that specific FQDN into high-threat mitigation mode (elevating CAPTCHA difficulty, challenging all datacenter/residential IPs, and rate-limiting POST endpoints).
   - The \d-gr-services\ FQDN remains in a normal/baseline traffic state, with minimal bot scrutiny and zero origin queuing.
3. **Cookie Scope Invariant:**
   - Imperva security cookies (\isid_incap_*\, \incap_ses_*\) are scoped to \.gvcworld.eu\ (the root domain), allowing cross-subdomain cookie trust.

## 3. System Architecture Adoption Strategy

### Phase 1: Dynamic Environment Variable Override (Immediate Hotfix)
The worker nodes already read the target domain dynamically via \BOOKING_PORTAL_URL\:
\\ash
BOOKING_PORTAL_URL=https://bd-gr-services.gvcworld.eu
\On slot opening days, configuring workers to point to \d-gr-services\ allows instant bypass of the localized \pk-gr\ traffic jam without requiring codebase modifications.

### Phase 2: Autonomous Regional Domain Failover (Control Plane Feature)
1. **Domain Pool Configuration:**
   Add a regional domain pool to the provider configuration:
   - Primary: \https://pk-gr-services.gvcworld.eu   - Secondary / Failover: \https://bd-gr-services.gvcworld.eu   - Tertiary: \https://in-gr-services.gvcworld.eu2. **Automated Health Check & Route Switching:**
   - When the Control Plane detects that \pk-gr-services\ response latency exceeds 3,000ms, or returns >20% 502/503/WAF challenge rates, the SaaS scheduler automatically instructs worker leases to target the failover endpoint (\d-gr-services\).
3. **Proxy Geolocation Matching:**
   - When routing through \d-gr-services\, route through South Asian residential proxies (e.g. Bangladesh ASN or regional ISP egress) to present a coherent network geographic footprint.

---
*Created: August 29, 2026 | Verified in Live Production Run | Owner: Knowledge Manager | Status: Adopted for Peak Strategy*
