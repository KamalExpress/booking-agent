# Visa Booking Automation Agent

This repository contains an automated agent designed to monitor and book visa appointments, along with mock portals for local testing and development.

## Project Structure

- **`booking-portal/`**: Contains `mock_portal.py`, a Flask server mocking the real visa booking website.
- **`internal-portal/`**: Contains `internal_api.py`, a Flask server mocking an internal CRM/Database that holds applicant details and SMS OTPs.
- **`operator-agent/`**: Contains the core python scripts:
  - `demo-operator.py` / `main_operator.py`: The actual bot logic that logs in and books a slot.
  - `slot_monitor.py`: A continuous background monitor that alerts you when slots open up.
  - `run_parallel.bat`: A script to launch a swarm of parallel bots to book multiple slots simultaneously.

## 1. Setup & Configuration

1. **Environment Setup:** Ensure you are using the provided Python virtual environment.
   ```powershell
   .\venv\Scripts\activate
   ```
2. **Configuration (`.env`):**
   Open the `.env` file in the root directory and ensure your settings are correct. 
   - Set `BASE_URL=http://localhost:5000` for local testing, or change it to the real production URL.
   - Set `MAX_SLOTS_TO_BOOK` to limit how many slots the parallel swarm will grab.
   - Set `MONITOR_INTERVAL_MINUTES` to control how often the slot monitor checks for openings.

## 2. Running Local Mock Portals (For Testing)

If you are testing locally, you must start the two mock portals in separate terminal windows.

**Terminal 1 (Mock Booking Portal):**
```powershell
cd booking-portal
..\venv\Scripts\python mock_portal.py
```

**Terminal 2 (Internal CRM/OTP Portal):**
```powershell
cd internal-portal
..\venv\Scripts\python internal_api.py
```

## 3. Running the Continuous Slot Monitor

If you just want to watch the calendar and get notified when slots become available, run the slot monitor. It will check every X minutes (based on your `.env`) and write an alert to `slots_notification.txt` in the root directory.

```powershell
cd operator-agent
..\venv\Scripts\python slot_monitor.py
```

## 4. Running the Booking Swarm

When slots are available, you can launch a swarm of parallel agents to book them instantly. The agents will pull applicants from the internal portal, fetch their OTPs, and book random available slots to avoid collisions.

```powershell
cd operator-agent
.\run_parallel.bat 3
```
*(Replace `3` with the number of parallel bot instances you want to spawn).*

The bots use a shared file-locking mechanism (`booked.txt` and `lock.txt`) to ensure they don't exceed the `MAX_SLOTS_TO_BOOK` limit defined in your `.env` file. Once the limit is reached, all parallel bots will safely terminate.
