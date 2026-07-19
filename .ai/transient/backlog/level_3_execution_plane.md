# Implementation Plan: Level 3 - Execution Plane (Worker Automation)

## Objective
Build the highly concurrent, headless Booker worker capable of automatically navigating the GVC portal, injecting applicant data, solving captchas, and polling the SaaS for relayed OTPs.

## Proposed Changes
### 1. Headless Booker Script (`ttttt/operator-agent/headless_booker.py`)
- **New Entrypoint:** Create `headless_booker.py` (leaving `gui.py` completely intact for desktop fallback).
- **Architecture:** Inherit from `BasePortalAdapter` (or similar interface) to prepare for VFS/BLS abstraction.
- **Workflow Steps:**
  1. **Fetch Task:** Poll the SaaS for a `Lease` containing the `BookingTask` (Applicant Data) and `PortalAccount` (GVC credentials).
  2. **Headless Login:** Automate the GVC login sequence headless via `playwright` or `curl_cffi`. Use the existing `CapSolverService` to bypass the login captcha silently.
  3. **Data Injection:** Navigate to the specific VAC endpoint and inject the Applicant payload (Surname, Passport, etc.).
  4. **TOS & Pre-OTP Check:** Click the Terms of Service. Check for secondary Captchas (route to CapSolver if found). Request the OTP.
  5. **OTP Polling:** Invoke `otp_service.py` to poll the SaaS `BookingTask` endpoint for the `otp_code` field to populate.
  6. **Final Submit:** Inject the fetched OTP and submit the final booking. Emit `BOOKING_SUCCESS` event to the SaaS.

### 2. Docker Deployment Strategy (`ttttt/operator-agent/Dockerfile.booker`)
- **Containerization:** Create a specific Dockerfile for the Booker worker (optimized for Playwright/Headless browser contexts if DOM automation is needed).
- **Scale Script:** Provide a `docker-compose.yml` snippet demonstrating how a SaaS Admin can spin up `booker-1`, `booker-2`, `booker-3` horizontally on the VPS.

## Verification Plan
- Use the existing `test_mode` endpoints or a mock local server to push a fake `BookingTask` to the `headless_booker.py` script.
- Verify the script correctly formats the GVC payload, attempts to solve the captcha, and pauses correctly waiting for the OTP.
