# Handling Login Edge Cases

Based on the logs, two new edge cases have been identified that cause unhandled exceptions, ultimately crashing the worker's assignment thread:

1. **Target API 503 Errors**: The target server (`pk-gr-services.gvcworld.eu`) temporarily went down and returned `503 Service Unavailable`. `urllib3` attempted to retry but eventually raised `urllib3.exceptions.MaxRetryError`. This bubbled up through `agent.login()` and crashed the worker.
2. **Playwright Frame Detached (ERR_ABORTED)**: During the manual captcha fallback, Playwright's `page.goto(url)` failed because the connection aborted or the frame detached before the load event fired.

To make the worker resilient, we need to handle these exceptions gracefully so the worker abandons the current assignment lease and moves on, rather than crashing entirely.

## Open Questions
None. The logs clearly show the stack traces and the source of the unhandled exceptions.

## Proposed Changes

### Operator Agent

#### [MODIFY] [slot_monitor.py](file:///d:/AI/bookingbot/bookingagent/ttttt/operator-agent/slot_monitor.py)
- Wrap the `agent.login()` call in a broad `try...except Exception as e:` block.
- If an exception occurs, log it locally, send an error log to the SaaS (`self.api.log_event(assignment_id, "LOGIN_EXCEPTION", ...)`), and gracefully `continue` the loop so the worker can pick up the next assignment instead of crashing.

#### [MODIFY] [main_operator.py](file:///d:/AI/bookingbot/bookingagent/ttttt/operator-agent/main_operator.py)
- In the `login()` method, wrap the `requests.post()` calls in a `try...except requests.exceptions.RequestException` block. If the target server is down (503), log the failure and return `False`.

#### [MODIFY] [captcha_service.py](file:///d:/AI/bookingbot/bookingagent/ttttt/operator-agent/captcha_service.py)
- In the `ManualCaptchaService.solve()` method, wrap the `page.goto(url)` call in a `try...except Exception as e:` block to catch Playwright networking/frame errors (like `ERR_ABORTED`). Return `None` if the page fails to load, allowing the system to handle the failure gracefully.

## Verification Plan
### Automated Tests
- N/A

### Manual Verification
- We can simulate a `503` by temporarily changing the target URL to an invalid endpoint or mocking the request to ensure the worker catches the error, logs it to the SaaS, and continues polling without terminating the Python process.
