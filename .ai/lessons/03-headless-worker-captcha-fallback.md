# Headless Worker CAPTCHA Fallback Crash (Lesson 03)

## Context
During Staging deployment, a `BrowserType.launch: Target page, context or browser has been closed` error occurred in the Headless Worker container.

The root cause was traced to the CAPTCHA resolution fallback sequence.

## The Sequence of Events
1. The SaaS assigned a task to the worker but provided an empty CapSolver API key (because it was seeded without a valid key).
2. The worker attempted to use `CapSolverService`, which naturally failed with `clientKey is required`.
3. As designed in `main_operator.py`, if the primary CAPTCHA service fails, the worker intelligently falls back to `ManualCaptchaService`.
4. `ManualCaptchaService` uses Playwright to launch a headed, visible browser (`headless=False`) so a human operator can manually solve the puzzle.
5. Because the worker was running inside a headless Docker container on a VPS (without an X11 server or GUI), Playwright catastrophically crashed attempting to open a window.

## The Resolution
We injected `ENV HEADLESS_WORKER=true` into the `operator-agent/Dockerfile`. 

In `main_operator.py`, the fallback sequence now checks this environment variable. If `HEADLESS_WORKER` is true, it gracefully logs an error and aborts the assignment instead of attempting to launch a headed browser and crashing the container.

## Key Takeaway
Whenever designing interactive fallbacks (like manual CAPTCHA solving or GUI prompts), always account for the execution context. Headless cloud workers must fail gracefully rather than attempting to render UI elements.

---
*Last Reviewed: Sprint 09 | Owner: Knowledge Manager | Confidence: High*
