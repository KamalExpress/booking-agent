# Implementation Plan: Notification & Slot History Enhancements

This plan outlines the architecture and UI updates required to make the SaaS and Tenant dashboards more informative regarding Push Notifications and historical Slot Availabilities.

## User Feedback Addressed
- **Notification Logs Configuration:** The system will use a new `SystemSetting` (`detailed_push_logging`) to toggle between logging only broadcast events (1 row per broadcast) or detailed per-device delivery status logs (1 row per device).
- **Tenant Access:** Tenant Admins will have a tailored view of the Push History page, showing only notifications dispatched to their tenant's staff. Super Admins will see a global view.
- **Readable Push Formatting:** The raw notification payload (e.g., `137:26` at `10:15`) will be parsed into user-friendly strings (e.g., *"1 Slot found on 21/07/2026 at 10:15 AM - Islamabad Visa Center for Type D Long Stay"*) using the global visa center configuration string.
- **Tenant Notification Quotas/Tracking:** `EventLog` records for `PUSH_SENT` will store `tenant_id` in their `payload` JSON structure, allowing us to easily query and display "Total Notifications Sent this Month" on the Tenant Dashboard for future tier-based pricing.

## Proposed Changes

### 1. Database & Core Logging (`app/models.py` & `app/notifications.py`)
- **[MODIFY]** `app/models.py`
  - Utilize the existing `EventLog` table with a new `event_type = 'PUSH_SENT'`. Store `tenant_id`, `success_count`, `title`, and `body` in the JSONB `payload`.
  - Introduce a new system setting `detailed_push_logging` (Boolean) to toggle detailed logs.
- **[MODIFY]** `app/notifications.py`
  - Update `send_push_notification` to accept the `db` session and user IDs. It will group users by `tenant_id` to log the `PUSH_SENT` broadcast event(s) in `EventLog`. If `detailed_push_logging` is enabled, it will also insert a row per device failure/success.

### 2. Push Notification History Page
- **[NEW]** `app/templates/notifications.html`
  - A clean, paginated data table showing: `Timestamp`, `Title`, `Message Body`, `Delivered To (Count)`, and `Scope (Global vs Tenant)`.
- **[MODIFY]** `app/routers/ui.py`
  - Add `GET /notifications` route. 
  - For `SUPER_ADMIN`: Fetch all `PUSH_SENT` logs.
  - For `TENANT_ADMIN`: Fetch only `PUSH_SENT` logs relevant to their Tenant ID.
- **[MODIFY]** `app/templates/base.html`
  - Add a "Push History" or "Notifications" link in the sidebar menu under the respective user roles.

### 3. Slot Details & History Pages
- **[NEW]** `app/templates/slot_history.html`
  - A dedicated page to view the historical timeline of slots found.
  - Filters for Visa Center and Date Range.
- **[NEW]** `app/templates/slot_detail.html` (or modal)
  - A detailed view for a specific `SlotAvailability` record (`GET /slots/{id}`).
  - Parses and neatly displays the nested JSON `slots_data` in a grid (showing the specific 15-minute intervals, e.g., 10:15-10:30, and slot IDs).
- **[MODIFY]** `app/routers/ui.py`
  - Add `GET /slots` (History view) and `GET /slots/{id}` (Detail view).
- **[MODIFY]** `app/templates/index.html` (Dashboard)
  - Update the "Recent Slots" cards to include a "View Details" button linking to `/slots/{id}`.
  - Add a "View Full History" link.
  - **[NEW UI WIDGET]**: Add a metric card to the Tenant and Admin dashboards displaying the "Push Notifications Sent this Month" count.

### 4. Push Notification Message Formatting (`app/routers/worker.py`)
- **[MODIFY]** `app/routers/worker.py`
  - When the worker parses `isselectable: True` and hits the `/api/worker/assignments/{id}/report-slot` endpoint, intercept the raw slot data.
  - Parse the time (`starttime`), map the `vac_id` and `type` to human-readable strings (using the global config), and format the push notification string cleanly (e.g. *"1 Slot found on 21/07/2026 at 10:15 AM - Islamabad Visa Center for Type D Long Stay"*).

### 5. Built-in DBMS via `sqladmin`
- **[MODIFY]** `requirements.txt`
  - Add `sqladmin` and `itsdangerous` (often needed for sqladmin session auth).
- **[NEW]** `app/admin.py`
  - Define `ModelView` classes for all our SQLAlchemy models (`Tenant`, `User`, `Assignment`, `WorkerNode`, `EventLog`, etc.).
  - Implement an `AdminAuth` backend that validates the existing JWT/Session cookie and ensures the user is `SUPER_ADMIN`.
- **[MODIFY]** `app/main.py`
  - Mount `sqladmin.Admin` onto the FastAPI app instance at `/admin`.

## Verification Plan
### Manual Verification
- Trigger a slot-found event (using a mock worker or test script).
- Verify the Web Push is sent and simultaneously logged in the `EventLog`.
- Navigate to `/notifications` as a Super Admin and verify the log appears with correct delivery counts.
- Click "View Details" on the newly found slot on the Dashboard and ensure the parsed JSON renders the specific time interval clearly.
