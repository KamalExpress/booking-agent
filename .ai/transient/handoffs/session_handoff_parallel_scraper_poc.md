# Session Handoff: Parallel Scraper Proof of Concept (POC)

## Context
We are upgrading the architecture to support massive concurrency so the system can book up to 150 slots simultaneously when a calendar opens. Before touching the sensitive `BookerEngine` and burning real OTPs/slots, we are going to build a Proof of Concept (POC) on the `SlotMonitorEngine` (the Scraper).

## Objectives for Next Session

1. **Implement the Slot Drop Mock**
   - In `ttttt/operator-agent/slot_monitor.py` (`SlotMonitorEngine.run`), intercept the slot checking loop (`agent.search_slots`).
   - If the date being checked is a weekday (not Saturday or Sunday), bypass the real `search_slots` logic and instantly mock the discovery of exactly `20` available slots.
   - Emit the `SLOT_FOUND` event to the SaaS. This will cause the backend's `auto_dispatch_queue` to go crazy and dispatch massive amounts of `BookingTask` objects.

2. **Implement Vertical Threading in the Scraper**
   - Refactor `SlotMonitorEngine.run` in `slot_monitor.py` to use a `concurrent.futures.ThreadPoolExecutor(max_workers=5)`.
   - The main `while not self._stop_event.is_set():` loop should solely be responsible for pulling leases (`self.api.get_next_lease()`) up to the maximum thread capacity.
   - Dispatch the login, scraping, and mocking logic into the executor pool.
   - *Note: Ensure network logging and exception handling are thread-safe and passed back correctly.*

3. **Harden the SaaS Backend (Concurrency Locks)**
   - Open `ttttt/cloud-saas/app/services/scheduler_service.py`.
   - In `_try_schedule_scraping`: Ensure that when querying for `Assignment`, `PortalAccount`, and `Proxy`, we use `.with_for_update(skip_locked=True)`.
   - Apply the same `skip_locked=True` logic to `_try_schedule_booking`.
   - Without these locks, the new multi-threaded scraper will query the SaaS concurrently, receive the exact same lease on multiple threads, and cause massive DB collisions.

## Testing the POC
- Start the SaaS backend.
- Run `headless.py` locally or via Docker.
- Observe the logs: It should pull multiple scraping assignments rapidly. It should find mock slots, emit events, and you should see the backend's `BookingTask` table explode with queued tasks safely without duplicate lease errors.

## Follow-up Action
Once the POC works flawlessly, this exact threading architecture and backend locking mechanism will be adapted for the `BookerEngine` (`headless_booker.py`) in subsequent sprints.
