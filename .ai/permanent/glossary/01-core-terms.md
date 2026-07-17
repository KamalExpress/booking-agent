# Project Glossary

## Control Plane (SaaS Backend)
- **Tenant:** A business entity (e.g., a travel agency) utilizing the platform. Tenants have their own users and assignments.
- **Super Admin:** The platform owner who manages all tenants, workers, and billing metrics.
- **Assignment:** A specific configuration (Visa Center, Date Range, Appointment Type) created by a Tenant that needs to be continuously scraped for slots.
- **Lease:** A temporary lock acquired by a Worker Node on an Assignment. Prevents two workers from scraping the exact same assignment simultaneously.

## Execution Plane (Worker Node)
- **Worker Node (Operator Agent):** A headless Python script running on an arbitrary machine (Windows, Linux, VPS, Raspberry Pi) that connects to the Control Plane to execute Assignments.
- **Capability:** A specific tag or feature a Worker possesses (e.g., `residential-ip`, `fast-cpu`). Assignments can be routed to workers based on capabilities.
- **SessionManager:** The network component in the worker that maintains cookies and TLS trust.
- **BrowserTrust:** The component in the worker that uses headless Playwright to solve JS challenges or Captchas before handing the cookies back to the SessionManager.

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
