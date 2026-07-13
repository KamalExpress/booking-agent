# Automation Gaps & Future Work Report

This document outlines the current limitations and gaps in the automated booking script (`operator.py`) that need to be addressed by developers before the script can be fully production-ready.

## 1. Missing Network Traces (HAR Gaps)

The current implementation was built using a HAR file that ended prematurely at the "search slots" step (`/api/v1/periodslot/slots`). Because of this, the following critical network requests are currently missing or implemented "blind":

### A. The "Send OTP" Request
- **Current State**: The `operator.py` script has a `request_otp` method that successfully polls our custom database API for the received SMS, but it **does not know how to tell the portal to send the SMS**. 
- **Required Action**: A developer needs to record a new HAR file capturing the exact moment the "Send OTP" button is clicked on the UI. Once the endpoint (e.g., `POST /api/v1/otp/send`) and payload are identified, uncomment and update the API call in `operator.py -> request_otp()`.

### B. The Final Booking Request
- **Current State**: The `book_appointment` method was reverse-engineered from the raw `form.html` source. It currently constructs an `application/x-www-form-urlencoded` payload with all the applicant data arrays (e.g., `applicants[][surname]`) and posts it to a guessed endpoint (`/appointments/add`).
- **Required Action**: The new HAR file must capture the final submission of the booking form to verify:
  1. The exact API endpoint (is it `/api/v1/appointment/book`, `/appointments/add`, etc?).
  2. The expected Content-Type (Form Data vs JSON).
  3. If there are any hidden CSRF tokens or other dynamic headers required in that final request.

## 2. Captcha Flow Clarification

- **Current State**: The script currently solves a single CAPTCHA during login and a second CAPTCHA during the final booking submission.
- **Required Action**: It was noted that a human operator clicks the CAPTCHA *before* clicking "Send OTP". The developer must review the new HAR to confirm exactly when the CAPTCHA tokens are validated by the backend. The `operator.py` script may need to be adjusted to solve and inject the CAPTCHA token into the "Send OTP" request rather than (or in addition to) the final booking request.

## 3. NopeCha Quota & Service Limits

- **Current State**: The provided NopeCha API key (`NOPECHA_API_KEY`) is active, but the NopeCha API is returning a `402 Payment Required` error with the message: `Feature unavailable for current plan`. This prevents the bot from logging in.
- **Required Action**: Upgrade the NopeCha billing plan to support the `recaptcha2` background solving feature via the API, or swap the `NopeChaService` implementation in `captcha_service.py` to use a different provider (like 2Captcha or AntiCaptcha). The architecture is already abstracted to support this easily.

## 4. Multi-Applicant Configuration

- **Current State**: The script pulls a single applicant's data (Name, DOB, Passport, etc.) from the `.env` file.
- **Future Action**: Integrate with the internal portal's future applicant management features. Instead of reading from `.env` or a local file, update `operator.py` to make an API call to the internal portal to fetch all applicants' data dynamically. The `main()` loop will then iterate over these returned applicant records and submit bookings sequentially.
