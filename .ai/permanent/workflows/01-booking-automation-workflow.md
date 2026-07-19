# Booking Automation Workflow & Gap Analysis

Based on the architectural review and iterative feedback, this report devises the complete workflow for the travel agent and outlines the exact architectural roadmap for the Booker workers. The immediate focus is exclusively on **GVC (Greece)**. 

*(For scalability and multi-portal integration like VFS, BLS, etc., see `02-architecture-scalability.md`)*.

---

## 1. The End-User (Travel Agent) Workflow
To achieve 80-90% automation, the travel agent will act proactively to queue applicants. The system will handle the reactive matching and highly parallelized booking.

### Phase A: Setup (Proactive)
1. **Client Onboarding:** The travel agent logs into the SaaS dashboard and enters the applicant's details into the **Client Directory**. Based on the GVC payload schemas, the required fields are:
   - **Personal Info:** Surname, First Name, Date of Birth, Gender, Nationality.
   - **Passport Info:** Passport Number, Passport Expiration Date.
   - **Contact Info:** Applicant Email, Phone Number Prefix, Phone Number.
   - **Appointment Target:** Visa Center (e.g., Lahore, ISB) and Appointment Type (e.g., Submission Schengen Visa, National Visa). 
   *(Note: Document verification appointments will be supported in a future phase).*
2. **Adding to the General Queue:** The agent adds the client to the **General Queue** for their desired Visa Center. The intent is: *"Book this applicant for the next available slot at this VAC."* 
   - *UI Note:* A "VIP Specific-Date Waitlist" feature should be visible in the UI but marked as **"Coming Soon"**.
3. **Delegation:** The agent steps away. Scrapers continuously monitor the portal in the background.

### Phase B: Execution (Automated & Parallelized)
4. **Slot Detected (Mass Drop):** Scrapers find multiple open slots (e.g., 5 slots) and send a `SLOT_FOUND` event to the SaaS.
5. **Task Generation (Mutually Exclusive):** The **Scheduler** scans the Queue, pulls the top 5 applicants waiting for that VAC, and instantly generates 5 separate `BookingTask`s. 
   - **Critical Mutual Exclusion:** The database leverages a strict unique constraint on `(visa_center, target_date, target_time, active_status)` and transaction locking (`SELECT FOR UPDATE SKIP LOCKED`) to guarantee two workers never attempt to book the exact same slot.
6. **Worker Assignment:** Available Booker workers instantly claim these 5 `BookingTask`s in parallel.
7. **Automated Booking:** The Bookers log in (via CapSolver), inject the applicants' data, trigger/input the OTP, and secure the bookings simultaneously.
8. **Notification (Inbox Integration):** 
   - The GVC portal emails the confirmation to the account email.
   - The SaaS logs an internal message to the tenant's **SaaS Inbox** (a must-have feature to be implemented) and sends a push notification.

---

## 2. Booker Worker Automation Pipeline & Deployment
### Deployment Model (Parallel Isolation)
To process 4-6 applicants simultaneously during a slot drop while avoiding WAF (Web Application Firewall) detection, the Booker nodes will be deployed as **multiple separate Docker containers**. 
- **Why Separate Containers?** Running a single container with heavily concurrent browsers shares the same OS-level fingerprint, network stack, and memory profile, making it highly susceptible to Imperva/Cloudflare bot detection. Separate, lightweight containers—each assigned its own Proxy and processing a single `BookingTask` at a time—provide much better isolation and scaling.

### Internal Pipeline per Booker Container:
1. **Headless Authentication:** The worker navigates to the GVC login page and utilizes **CapSolver** to bypass the login captcha silently. (This reuses the proven logic from the Scraper implementation). *Note: A new headless script (e.g., `headless_booker.py`) will be created for this, borrowing logic from `gui.py`. The original `gui.py` will be kept intact for desktop fallback use.*
2. **Data Injection & Navigation:** Using documented HAR payloads, it hits the GVC booking endpoints (or automates the DOM) to inject the VAC, Appointment Type, and Applicant details.
3. **TOS & Pre-OTP Check:** 
   - The worker checks the TOS agreement.
   - It checks for any secondary Captcha challenge (resolving via CapSolver if present) and clicks the button to trigger the SMS OTP.
4. **OTP Relay Pipeline & Race Conditions:**
   - The SMS OTP is sent to a physical or virtual phone. 
   - *OTP Race Condition Note:* For highly parallel booking (e.g., booking 5 applicants at once), sharing a single phone number creates a bottleneck or race condition where multiple OTPs arrive simultaneously. For maximum success rates, ideally there should be a 1:1 mapping of phone numbers to applicants (potentially using virtual number APIs). The exact solution for this is pending further research.
   - The phone/gateway POSTs the incoming SMS to a dedicated SaaS webhook.
   - The SaaS maps the incoming OTP to the active `BookingTask` and stores the `otp_code` directly as a field on the `BookingTask` record.
   - The Booker worker (via `otp_service.py`) polls the SaaS for its specific `BookingTask`'s OTP.
5. **Final Confirmation:** The worker parses the success response, marks the `BookingTask` as `SUCCESS` (using the standardized system Enums), and alerts the Scheduler.

---

## 3. Control Plane Gaps (SaaS Architecture)
To support this highly automated, parallel flow, the following must be implemented in the SaaS backend:

1. **Applicant Model & UI:** Table for GVC client fields.
2. **Booking Queue Model:** A FIFO queue mapping applicants to a target VAC. 
3. **SaaS Inbox System:** An internal messaging module for tenant notifications.
4. **Scheduler Auto-Routing (Parallel):** Ensure the `SLOT_FOUND` event handler loops through all available slots in the drop, dequeues multiple applicants, and creates `BookingTasks` with strict unique constraints.
5. **OTP Webhook Integration:** 
   - Create `POST /api/webhooks/otp` to receive payloads from the SMS gateway.
   - Update the `BookingTask` schema to include `otp_code` (nullable string).
6. **Account Mapping Rules:** Add a policy in the Scheduler that limits how many applicants are processed per `PortalAccount` (e.g., max 4-6 applicants per GVC login email).
