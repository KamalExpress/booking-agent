# Architecture 11: Alamia Copilot & HITL Orchestration Engine

## System Overview
The **Alamia Copilot Architecture** provides an integrated operational intelligence and Human-in-the-Loop subsystem for Cloud SaaS. It separates deterministic infrastructure from generative reasoning.

---

## 1. Architectural Topology

```text
               CLIENT / PWA (Browser & Mobile)
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
        [ WebSockets ]               [ REST Endpoints ]
       /ws/dashboard                 /api/v1/hitl/*
       /ws/monitor                   /api/v1/copilot/*
               │                             │
               └──────────────┬──────────────┘
                              ▼
                   [ FastAPI Control Plane ]
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
[ HITL State Engine ]  [ Copilot Orchestrator ] [ FastMCP Tools ]
  OTP Challenges         Quick Actions (0 LLM)   Active Leases
  Ephemeral Purge        ai.alamiaconnect.com    Portal Health
  Dynamic Timers         Fallback Handler        Maintenance
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                     [ PostgreSQL Database ]
                     tenants (has_ai_copilot)
                     otp_challenges
                     booking_tasks
```

---

## 2. Zero-SPOF Graceful Degradation Invariant
The core automated scraping, slot search, and booking engine must **NEVER fail** due to AI downtime:
1. **Deterministic HITL Route:** Submitting OTPs and unfreezing resources bypasses the AI completely.
2. **AI Server Failure Mode:** If `https://ai.alamiaconnect.com/` is offline or times out (3.5s timeout threshold):
   - The Copilot chat returns a structured fallback message.
   - All 1-click action buttons remain fully functional.
   - No 500 error or container crash is triggered.

---

## 3. Database Schema Specification

### `otp_challenges` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | Integer | Primary Key | Auto-increment ID |
| `challenge_id` | String | Unique Index, Not Null | Unique UUID e.g. `otp_634c71fb80a4` |
| `booking_task_id` | Integer | FK `booking_tasks.id` | Target booking task |
| `tenant_id` | Integer | FK `tenants.id`, Nullable | Owning tenant |
| `applicant_name` | String | Nullable | Applicant full name |
| `visa_center` | String | Nullable | Visa application center ID/code |
| `appointment_type` | String | Nullable | Target visa category |
| `status` | String | Index | `PENDING`, `SUBMITTED`, `CONSUMED`, `EXPIRED`, `CANCELLED` |
| `otp_code` | String | Nullable | Ephemeral OTP code; wiped upon `CONSUMED` |
| `expires_in_seconds` | Integer | Default 300 | Dynamic worker-aligned timeout |
| `expires_at` | DateTime | Not Null | Computed expiration deadline |
| `created_at` | DateTime | Default UTC now | Creation timestamp |
| `submitted_at` | DateTime | Nullable | When staff entered the code |
| `consumed_at` | DateTime | Nullable | When worker used the code |

### `tenants` Enhancement
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `has_ai_copilot` | Boolean | Default True | Subscription tier gating for Alamia Copilot Pro |
