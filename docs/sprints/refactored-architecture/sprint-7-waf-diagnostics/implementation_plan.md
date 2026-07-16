# WAF Bypass & Diagnostics (Network Activity Capture)

After analyzing the `HAR` file and the worker logs from the VPS, the `403 Forbidden` from Incapsula with an `incident_id` indicates that the worker is failing the initial WAF check. Because the worker is headless and uses `curl_cffi`, it cannot execute JavaScript. If Imperva detects the VPS IP (e.g., Hetzner datacenter) and serves a JavaScript challenge on the first `GET` request, the worker fails to generate the `visid_incap` cookie required for the login `POST`.

To resolve this and gain full visibility into what Imperva is sending to the VPS, I will implement **Worker Network Activity Capturing (HAR-like Logging)** as you requested.

## Proposed Changes

### 1. Worker Node: Network Interception & Logging
I will modify `D:\AI\bookingbot\bookingagent\ttttt\operator-agent\main_operator.py` to intercept and log all `curl_cffi` HTTP traffic:
- **Request Logger**: Create an interceptor that hooks into the session to record the Method, URL, Request Headers, Request Payload, Response Status, Response Headers, and Response Body.
- **JSON Dump**: The worker will save this captured network traffic into a structured `debug_network_<timestamp>.json` file (mimicking the utility of a `.har` file without needing Playwright).

### 2. Worker -> SaaS Data Transmission
- Update the worker's `report_status` or task completion API logic in `worker_node.py` to upload this JSON file (or its contents) to the SaaS backend when a task fails (or completes).

### 3. SaaS Admin: Storage & Download UI
- **Backend**: Add an endpoint in the SaaS API (`cloud-saas/app/routers`) to receive and store these network capture logs per assignment/worker.
- **Admin UI**: Add a **"Download Worker HAR/Log"** button in the SaaS Admin Panel (e.g., on the Assignments or Accounts view) so you can directly download and inspect the raw requests and responses the worker encountered.

## User Review Required
> [!IMPORTANT]
> Since the worker and SaaS run on the same VPS, the easiest approach is to have the worker `POST` the debug log to the SaaS API. Are you comfortable with me updating the SaaS database schema (adding a `debug_log` column to the assignment or account model) and API to handle this upload? Or would you prefer the files simply be saved to a shared Docker volume?

If you approve this plan, I will implement the interceptor and the UI download button immediately so we can see exactly what the VPS is receiving from Imperva.
