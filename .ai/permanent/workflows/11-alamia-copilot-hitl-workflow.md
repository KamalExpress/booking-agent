# Workflow 11: Alamia Copilot & Human-in-the-Loop (HITL) OTP Verification

## Overview
The **Alamia Copilot** is a two-way operational assistant and Human-in-the-Loop (HITL) orchestration engine embedded directly inside Cloud SaaS. Its primary operational mission is to **eliminate booking failure at the OTP/2FA verification step** by proactively alerting agency staff via mobile/desktop PWA push notifications, presenting an interactive countdown card, and injecting the verification code into the waiting Booker worker in real time.

---

## 1. Core Architectural Principle
> **"HITL is deterministic infrastructure; Alamia Copilot is the intelligent, proactive UX layer on top of it."**

The critical OTP booking path has **zero dependency on the LLM or AI subsystem**:
- Submitting an OTP goes through a dedicated deterministic REST API (`POST /api/v1/hitl/challenges/{id}/submit`).
- The LLM never touches, parses, or stores verification codes.
- 1-click preset actions (`[System Health]`, `[Active Leases]`, `[Unfreeze Resources]`) execute with **0 LLM calls**.
- Free-form conversational reasoning queries the private internal LLM (`https://ai.alamiaconnect.com/`) with strict timeouts and **Zero-SPOF Graceful Degradation** (the system functions 100% reliably even if the AI server is offline).

---

## 2. OTP Challenge Lifecycle State Machine

```text
       [ BOOKER WORKER REACHES OTP SCREEN ]
                         │
                         ▼
                 ┌──────────────┐
                 │   PENDING    │ <── challenge_id = UUID, expires_at = now + expires_in_seconds
                 └──────┬───────┘
                        │
         ┌──────────────┴──────────────┐
         │ (Human submits OTP code)    │ (Timeout expires or cancelled)
         ▼                             ▼
  ┌──────────────┐              ┌──────────────┐
  │  SUBMITTED   │              │   EXPIRED    │
  └──────┬───────┘              └──────────────┘
         │
         │ (Worker consumes & submits to portal)
         ▼
  ┌──────────────┐
  │   CONSUMED   │ (otp_code immediately purged from database)
  └──────────────┘
```

---

## 3. End-to-End Operational Workflow

### Step 1: Worker Telemetry Trigger
When the headless booking worker reaches the SMS/Email OTP verification modal on the visa portal:
1. It sends an `OTP_REQUIRED` event to the SaaS Control Plane:
   ```json
   {
     "event_type": "OTP_REQUIRED",
     "payload": {
       "booking_task_id": 42,
       "visa_center": "138",
       "appointment_type": "Long-Term Type D",
       "applicant_name": "Ahmed Rafique",
       "expires_in_seconds": 300
     }
   }
   ```
2. The SaaS Control Plane automatically creates an `OTPChallenge` record with a unique UUID (`otp_...`), calculates `expires_at = utcnow() + timedelta(seconds=300)`, and sets `status = "PENDING"`.

### Step 2: Multi-Channel Real-Time Outreach
- **Channel A: Realtime WebSocket Broadcast**
  Dispatches an `OTP_CHALLENGE_CREATED` event to all open dashboard tabs. The Alamia Copilot drawer auto-slides open, displays a pulsing amber badge, and plays an alert chime.
- **Channel B: Privacy-Safe Mobile Web Push**
  Sends an urgent Web Push notification to agency staff devices with lockscreen-safe text:
  - **Title:** `⚠️ Booking Verification Required`
  - **Body:** `Alamia Copilot: Action needed to finalize visa appointment. Tap to enter code.`
  - **URL:** `/?open_copilot=true&challenge_id=otp_...`

### Step 3: Interactive Drawer & Dynamic Countdown
In the Copilot drawer, staff sees the **Active Challenge Card**:
- **Dynamic Timer:** Reads `expires_at` and displays a color-coded **`MM:SS`** countdown (green $	o$ amber $	o$ flashing red under 60s). It aligns strictly with the worker's configured timeout (e.g. 300s).
- **Context Details:** Displays applicant name, visa center, and appointment type.
- **Direct Input:** Large numeric keypad input with an instant `[ Submit ]` button.

### Step 4: Submission & Worker Resumption
1. Staff enters the 6-digit code and clicks Submit.
2. The frontend calls `POST /api/v1/hitl/challenges/{challenge_id}/submit` (0 LLM calls).
3. The SaaS marks `status = "SUBMITTED"` and updates `booking_tasks.otp_code`.
4. A WebSocket event (`OTP_CHALLENGE_SUBMITTED`) wakes up the worker immediately.
5. The worker consumes the code, enters it on the visa portal, calls `POST /api/v1/hitl/challenges/{challenge_id}/consume`, and the temporary code is **immediately purged from memory**.

---

## 4. Productization & Tier Gating (`Tenant.has_ai_copilot`)
- Gated via `Tenant.has_ai_copilot` in `models.py`.
- SaaS admins can enable or disable Copilot access per agency tenant.
- Tenants without this feature receive a polite upgrade prompt when querying the assistant.
