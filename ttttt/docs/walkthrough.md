# Automated Booking Agent Walkthrough

The initial implementation of the browserless booking agent has been completed. Here is a summary of the work done:

## Changes Made

1. **Project Setup**:
   - Created `requirements.txt` with dependencies (`requests` and `python-dotenv`).
   - Created `.env.example` to provide a template for credentials and appointment details.

2. **Network Analysis**:
   - Parsed the `login-data-entry-search-slots.txt` HAR file to extract exact API endpoints and JSON payloads for logging in and searching for slots.
   - Reversed engineered `form.html` to extract the fields required for the final `book_appointment` POST payload.

3. **Captcha Solving Architecture (`captcha_service.py`)**:
   - Implemented an abstract `CaptchaService` base class.
   - Integrated the `NopeChaService` to handle reCAPTCHA solving silently via API requests.

4. **Core Automation Script ([`operator.py`](file:///f:/Playgrounds/bookingbot/ttttt/operator.py))**:
   - **Environment Configuration**: Loads all credentials, booking settings, and applicant data (`APPLICANT_EMAIL`, `APPLICANT_PASSPORT`, etc.) safely from the `.env` file.
   - **Session Management**: Configured a `requests.Session` with realistic `User-Agent` to maintain cookies across API calls.
   - **Booking Payload**: Implemented the final `book_appointment` step, mapping the `.env` parameters exactly to the form fields expected by the portal (`application/x-www-form-urlencoded`).
   - **Logging**: Detailed logging configured for all requests and responses (including NopeCha integration) to aid in future debugging.
   - **Login**: `login()` method hits the extracted `/api/v1/auth/login` endpoint with the username, password, and captcha token.
   - **Search Slots**: `search_slots()` executes the `PUT` request to `/api/v1/periodslot/slots` with the exact payload structure found in the HAR data.
   - **OTP Handling**: Created `request_otp()` which halts the process and prompts you in the console to manually input the SMS OTP.
   - **Booking**: Added a placeholder `book_appointment()` method for the final step.

## Next Steps / Future Work
- The NopeCha plan needs to be upgraded or an active key provided to bypass the 401 Unauthorized login issue.
- **Multi-Applicant Support**: The applicant data currently housed in `.env` will eventually be replaced by a dynamic API call to the internal portal's applicant management system, allowing the agent to fetch and process multiple applicants automatically.

## How to Run the Demo

> [!TIP]
> **Step 1: Activate Virtual Environment**
> To avoid dependency conflicts, all components share a single virtual environment at the root folder.
> ```powershell
> cd f:\Playgrounds\bookingbot\ttttt\
> .\venv\Scripts\Activate.ps1
> ```
> 
> **Step 2: Start the Internal Portal (Terminal 1)**
> With the venv activated:
> ```powershell
> cd internal-portal
> python internal_api.py
> ```
> 
> **Step 3: Start the Booking Portal (Terminal 2)**
> Open a new terminal, activate the venv again (`.\venv\Scripts\Activate.ps1`), and run:
> ```powershell
> cd booking-portal
> python mock_portal.py
> ```
> *Visit `http://localhost:5000` in your browser to see the live slots visualizer.*
> 
> **Step 4: Run the Operator Agent (Terminal 3)**
> Open a new terminal, activate the venv again, and run:
> ```powershell
> cd operator-agent
> python operator.py
> ```
> 
> *Once the operator finishes, refresh your browser at `http://localhost:5000` to see the slot turn grey!*
