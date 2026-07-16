# Sprint Walkthrough: WAF Network Capture Diagnostics

In this sprint, we implemented a mechanism for our headless workers to act like fully-fledged DevTools Network Captures. This allows us to securely collect and inspect the precise HTTP payloads and headers that the Imperva WAF is returning when we get the `403 Forbidden` error on the VPS.

## Changes Made

### 1. The Interceptor (`operator-agent/main_operator.py`)
- Monkey-patched the underlying `curl_cffi` session `request` method.
- All HTTP `GET` and `POST` traffic (including headers, parameters, JSON payloads, and response bodies) is recorded in a JSON-compatible format.
- Exposed a `get_network_logs()` method to retrieve the session's traffic at the end of an assignment.

### 2. Secure Transmission (`operator-agent/api_client.py` & `slot_monitor.py`)
- Created `api_client.submit_network_logs()` which utilizes the worker's HMAC-signed authorization to post logs directly to the SaaS server.
- Wrapped the core assignment logic in `slot_monitor.py` within a `finally` block. Regardless of whether the worker succeeds, crashes, or gets blocked by Imperva, the worker will transmit whatever network traffic it captured right before terminating the loop.

### 3. Storage & Administration (`cloud-saas/app/...`)
- **Database**: Introduced the `WorkerLog` model and applied it to the database initialization.
- **API Endpoints**: Created `POST /api/v1/worker/worker-logs` for headless upload. Added `GET /api/v1/admin/worker-logs/{log_id}/download` and `POST /api/v1/admin/worker-logs/clear` for SaaS Admin management.
- **UI Tab**: Updated the `worker_detail.html` page to feature a new **"Network Captures"** tab. Administrators can now browse intercepted sessions, note their size, and download the raw `.json` files to trace the WAF block point-by-point.

## What's Next?
When you push this update and the headless worker attempts its next login, it will intercept the `403 Forbidden` response and upload the network trail. You can then download it via the SaaS Worker Detail page and examine exactly what Imperva blocked (or if it served a JS challenge).
