# GUI Tool Impact Analysis (`gui.py`)

As we implement the massive automation scaling plan (DAG Tasks, Waitlist models, Headless Bookers), the underlying worker libraries will undergo significant refactoring. While the goal is to create a new `headless_booker.py` script and leave `gui.py` as a desktop fallback tool, **`gui.py` relies on shared core libraries (`api_client.py`, `slot_monitor.py`)**. 

Therefore, it is inevitable that `gui.py` will experience some breaking changes if not carefully patched. This document lists all planned architectural changes and their direct impact on the GUI tool.

---

## 1. Provider Adapter Pattern Refactoring
**The Change:** To support VFS, BLS, etc., we are implementing a `PortalAdapter` base class (as defined in `02-architecture-scalability.md`). `api_client.py` and `slot_monitor.py` will be refactored to route commands through these adapters.
**Impact on `gui.py`:**
- `gui.py` currently instantiates `SlotMonitorEngine` directly. 
- **Breaking Risk:** The engine initialization signature will likely change to require a `provider` flag. 
- **Required Patch:** `gui.py` will need a dropdown menu added to its interface (e.g., "Select Portal: GVC / VFS") so it knows which adapter to pass to the engine.

## 2. API Payload Evolution (SaaS Control Plane)
**The Change:** The SaaS backend is updating the `BookingTask` model (adding `otp_code`) and changing how `SLOT_FOUND` events map to the new Applicant Waitlist Queue.
**Impact on `gui.py`:**
- `gui.py` has a **Test Mode** (specifically `test_slot_found()` and `test_no_slots()`) which simulates events.
- **Breaking Risk:** If the SaaS expects a new payload schema for a `SLOT_FOUND` event (e.g., requiring specific `visa_center` context to trigger the Waitlist properly), the current test buttons in the GUI will return `400 Bad Request` or fail silently.
- **Required Patch:** Update the `_run_test_event` JSON payloads in `gui.py` to conform to the new SaaS Event schema.

## 3. The OTP Pipeline
**The Change:** The headless worker will use `otp_service.py` to silently poll the SaaS API for the OTP (which was pushed via the Android Webhook).
**Impact on `gui.py`:**
- When a human is running `gui.py` on their desktop as a fallback, they might not have the Android Webhook hooked up to their personal phone number.
- **Breaking Risk:** The worker engine might indefinitely poll the SaaS for an OTP that will never arrive via the webhook.
- **Required Patch:** `gui.py` needs to inject an override flag into the engine. When running in "GUI Mode", instead of polling the SaaS for the OTP, the GUI should pop up a `ctk.CTkInputDialog` asking the human operator to manually type the OTP they just received on their phone.

## 4. `ManualCaptchaService` Integration
**The Change:** Headless workers will default to `CapSolverService`.
**Impact on `gui.py`:**
- **Breaking Risk:** If we hardcode CapSolver directly into the core `api_client.py` request pipeline, `gui.py` will lose its ability to pop open the Playwright browser for the human operator.
- **Required Patch:** We must maintain strict Dependency Injection for the `CaptchaService`. `gui.py` must explicitly pass the `ManualCaptchaService` instance into the `SlotMonitorEngine` when initializing it, overriding the headless CapSolver default.

---
*Reference this document when finalizing Level 3 (Worker Automation) of the Implementation DAG to ensure the desktop GUI fallback remains operational.*
