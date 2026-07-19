# Architecture Scalability Report

## Overview
While the immediate development focus is heavily tailored toward **GVC (Greece)**, the core value of the Kamal Express platform relies on its ability to rapidly onboard new providers such as **VFS Global**, **BLS International**, and **TLScontact**.

This report outlines the scalability gaps in the current architecture and the adjustments required to seamlessly transition to a multi-portal ecosystem without fragmenting the codebase.

---

## 1. Abstraction of Worker Payloads (Execution Plane)

### The Current Gap
Currently, terms like `visa_center` and specific date formatting assume a GVC-like structure. If a Booker worker is hardcoded to navigate GVC DOM elements or hit GVC-specific API payloads, adding VFS will require either duplicating the entire worker binary or heavily patching it with `if/else` statements, which leads to brittle code.

### The Required Adjustment
We must enforce a strict **Provider Interface Pattern** in the `operator-agent` (Worker Node).
- The SaaS Scheduler should be responsible for sending a provider-agnostic `BookingTask`.
- The Worker Node should implement an abstract `PortalAdapter` base class. 
- During task assignment, the worker dynamically loads the correct adapter (e.g., `GvcAdapter`, `VfsAdapter`) based on the `provider` field.
- **Action Item:** Refactor the worker's `api_client.py` and `slot_monitor.py` to inherit from `BasePortalAdapter`. The core worker engine only calls `.login()`, `.check_slots()`, and `.submit_booking()`, leaving the specifics (DOM navigation, HAR payloads) completely encapsulated inside the individual provider scripts.

## 2. Dynamic Field Schemas for Applicants (Control Plane)

### The Current Gap
The `Applicant` database table we are designing for GVC includes specific fields (e.g., `Appointment Type` using GVC enums like 0, 2, 26). Different portals require vastly different data points. For example, VFS might require a GWF number or biometric enrollment dates, whereas Italy BLS might need specific regional sponsor details.

### The Required Adjustment
The Applicant directory cannot use a rigid SQL schema for portal-specific data.
- **Core Fields:** Keep strictly universal fields as standard SQL columns (Name, Passport Number, DOB, Nationality).
- **Dynamic Metadata:** Implement a `JSONB` column named `provider_metadata` in the `Applicant` table.
- **UI Form Builders:** The SaaS UI should render the Applicant Intake Form dynamically based on the selected target provider, mapping custom fields into the `provider_metadata` JSON blob. This ensures the database schema doesn't need migration every time a new portal is supported.

## 3. Scraper & Booker Routing Rules

### The Current Gap
As we add VFS and BLS, the SaaS needs to ensure that a `BookingTask` for VFS is not accidentally sent to a worker node that only has the GVC automation scripts updated, or to a worker using a proxy that is banned on VFS but fine on GVC.

### The Required Adjustment
The `SchedulerDecision` logic must be expanded to include **Provider-Aware Routing**.
- **Worker Capabilities (`worker_nodes`):** Workers must report their supported providers during the heartbeat (e.g., `{"supported_providers": ["GVC", "VFS"]}`).
- **Proxy Health Scopes:** The `health_score` on the `Proxy` and `PortalAccount` models must be scoped by provider. A proxy might have a health score of 0 for Imperva (VFS) but 100 for Cloudflare (BLS).
- **Action Item:** Refactor `ScoringPolicy` so that the `lease_service.py` strictly filters workers and proxies by the `provider` string attached to the `Assignment` or `BookingTask`.

## 4. Captcha Service Routing

### The Current Gap
Currently, `captcha_service.py` is somewhat tailored. GVC might use ReCaptcha V2, but VFS might shift to hCaptcha, Cloudflare Turnstile, or DataDome sliders.

### The Required Adjustment
- The `CaptchaService` interface is already cleanly abstracted in the codebase. However, the `PortalAdapter` (mentioned in Point 1) must be responsible for explicitly requesting the *type* of Captcha challenge it faces.
- The Worker must be able to dynamically switch between `CapSolver` (for ReCaptcha) and other services (like 2Captcha or Anti-Captcha) depending on the `provider`'s defense mechanism.

## Summary
By enforcing **Adapter Patterns** on the Worker nodes and utilizing **JSONB dynamic forms** in the SaaS Control Plane, the architecture can scale to infinite visa portals without breaking existing workflows or requiring monolithic database migrations.
