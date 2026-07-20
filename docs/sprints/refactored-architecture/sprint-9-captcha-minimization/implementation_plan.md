# Session Reuse and CAPTCHA Minimization

Based on the logs and AI opinion, the headless worker is currently discarding perfectly valid sessions and unnecessarily re-running the full login flow (pre-flight navigation + CapSolver) on every assignment. This causes rapid depletion of CapSolver credits and increases the risk of WAF bans due to repeated login attempts.

This plan aims to implement intelligent session reuse and add circuit breakers for failed logins.

## Proposed Changes

### 1. Add Session Validation (`OperatorAgent`)

We will add a mechanism to check if the cached session cookies are still valid before attempting a full login.

#### [MODIFY] [main_operator.py](file:///d:/AI/bookingbot/bookingagent/ttttt/operator-agent/main_operator.py)
- **Add `is_authenticated(self)` method**:
  - Makes a lightweight authenticated API request (e.g., a dummy payload to `/api/v1/periodslot/slots`) to verify session validity.
  - If the request returns `200 OK`, the session is fully valid.
  - If it returns `401 Unauthorized`, the session has expired.
  - **WAF Integration**: If the check hits a WAF block (`403/502`), it will intelligently trigger `refresh_waf_cookies()` to refresh the Incapsula TLS fingerprint without throwing away the application session cookies, and then retry the check once.
- **Update `login(self)`**:
  - Insert `if self.is_authenticated(): return True` at the very beginning. This will entirely bypass pre-flight navigation and CAPTCHA solving if the session is still active.

### 2. Implement CAPTCHA Circuit Breaker

To prevent the scheduler from creating an infinite CAPTCHA retry loop if an account's credentials become invalid or temporarily banned, we will add a cooldown state.

#### [MODIFY] [worker.py (SaaS API)](file:///d:/AI/bookingbot/bookingagent/ttttt/cloud-saas/app/routers/worker.py)
- In the `submit_logs` endpoint, when a `LOGIN_FAILED` event is received:
  - Locate the associated `ScraperAccount`.
  - Set its `status` to `"Cooldown"` (or `"Error"` depending on existing enums). This will prevent the assignment scheduler from instantly re-assigning the broken account to another worker and burning another CAPTCHA solve.

## Verification Plan

### Manual Verification
- Start the Cloud SaaS backend and worker.
- Monitor the worker console logs on the first run: it should perform the standard login flow (solving CAPTCHA).
- Allow the assignment to complete. When the worker fetches its next assignment for the same account, the console should log: `Validating existing session...` -> `Session is fully valid. Bypassing login.`
- Verify that CapSolver is only invoked once per account lifecycle instead of every assignment cycle.
