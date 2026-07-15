# Push Notifications & Diagnostics Implementation Plan

You raised great points regarding testing these critical system functions without wasting real worker cycles or CAPTCHA funds! 

I propose we create a dedicated **Diagnostics & Testing** page in the UI that provides a clean interface for you to run on-demand health checks and simulations. In addition, we will implement the missing push notification events on the worker side.

## Proposed Features for Diagnostics Mode

1. **Test WebPush Notifications**
   - Send a direct dummy push notification to your current device to verify that the ServiceWorker and `VAPID` keys are correctly configured.
2. **Test Captcha Service (CapSolver)**
   - Securely decrypt your CapSolver API key and call the `https://api.capsolver.com/getBalance` endpoint. This will verify that the API key is valid, your account isn't banned, and you have sufficient funds.
3. **Simulate "No Slots Found"**
   - Triggers the new push notification logic: *"No Slots available; last checked: [timestamp]"*.
4. **Simulate "Slot Found"**
   - Triggers the push notification: *"Slots are available; you can try booking now!"*
   - Additionally, pauses the selected Assignment to demonstrate how the system prevents further worker runs and saves Captcha tokens.

## Open Questions

- Where would you like the "Diagnostics" page located? (e.g., A new tab in the global Settings page, or a standalone link in the main sidebar?)
- For the "Simulate Slot Found" test, should it pause *all* active assignments, or just let you pick an assignment ID from a dropdown to pause?

## Proposed Changes

### 1. Code Cleanup (Push Notifications)
#### [NEW] [notifications.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/notifications.py)
Extract the `VAPID` initialization and `pywebpush` wrapper logic from `main.py` into a standalone module. This prevents circular imports and allows `worker.py` to send push notifications safely.

### 2. Worker Event Logging
#### [MODIFY] [slot_monitor.py](file:///d:/AI/bookingbot/bookingagent/ttttt/operator-agent/slot_monitor.py)
- When the date range loop finishes and `slots_found == False`, send a `"NO_SLOTS_FOUND"` event log to the SaaS backend.

#### [MODIFY] [worker.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/routers/worker.py)
- Update the `/logs` endpoint to intercept `"NO_SLOTS_FOUND"` and dispatch a push notification to all users in the tenant.
- Intercept `"SLOT_FOUND"`. Dispatch a push notification to all users and automatically update the corresponding `Assignment` status to `"Paused"`.

### 3. Diagnostics UI
#### [NEW] [diagnostics.html](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/templates/diagnostics.html)
- A new UI template containing cards for each of the 4 test mode actions.

#### [MODIFY] [ui.py](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/routers/ui.py)
- Add GET `/diagnostics` to render the page.
- Add POST endpoints for `/api/diagnostics/test-push`, `/api/diagnostics/test-captcha`, and `/api/diagnostics/simulate-slots` to perform the backend simulation logic.

## Verification Plan
1. We will visit the new `/diagnostics` page in the SaaS.
2. Click the "Test Captcha" button and expect to see a balance returned on-screen.
3. Click "Simulate Slot Found" and expect to receive a push notification + see the assignment automatically Paused in the database.
