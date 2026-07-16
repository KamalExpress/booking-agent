# Session Handoff: Kamal Express Cloud SaaS

## Current State & Context
We are migrating a Windows Desktop Booking Bot to a **Cloud-based SaaS Application** (FastAPI backend + Vanilla JS/HTML frontend). The bot uses a threaded `SlotMonitorEngine` with Playwright (headless) to constantly scrape a target website for booking slots.

The main challenge encountered during this session was **Handling Captchas in a Headless/SaaS Environment**.

## What Was Accomplished
1. **Log Observability**: Built a custom `MemoryLogHandler` that pipes standard Python `logging` directly from the background threads to a fast, in-memory queue. These logs are polled by the frontend and displayed in a **Live Bot Terminal** for Super Admins.
2. **Staff Permission System**: Added a `can_solve_captcha` boolean to the database via raw SQL injection. The backend schemas, API endpoints, and frontend Staff Modals were updated to support toggling this permission.
3. **Manual Bot Trigger**: Rewrote the thread sleeping mechanism to use `threading.Event()`. Added a **"Run Bot Now"** button to the UI that instantly bypasses the sleep timer and wakes the bot up for immediate execution.
4. **Captcha Engine Setup**: 
   - Built a blocking `global_captcha_state` mechanism that freezes the Playwright scraping thread when a Captcha is detected.
   - Built a frontend polling loop (`checkPendingCaptcha`) that detects the blocked state and pops up a Google reCAPTCHA v2 Modal for the user to solve manually.
5. **Debugging & Limitations**: 
   - Traced why the Google widget wouldn't physically render: **"Invalid domain for site key"**. 
   - Confirmed that the target website heavily restricts their sitekey to their own domain. Unlike the previous Desktop App (which spoofed headers), standard web browsers forbid Javascript from spoofing the `Origin`/`Referer` headers. 

## What is Pending (The Path Forward)
The user has decided to pursue a hybrid of **Option 1 (Automated API)** and **Option 3 (Chrome Extension)** to solve the domain restriction issue.

### 1. Option 1: Automated 3rd-Party Solving (Recommended default)
- **Goal**: Integrate `NopeChaService` (or 2Captcha/CapSolver).
- **Task**: 
  - Ensure the user has an active API key from the chosen service.
  - Update the `MonitorConfig` in the database to default back to `strategy = "AUTO"`.
  - Validate that the `NopeChaService.solve()` logic correctly intercepts the sitekey and URL, sends it to the API, and successfully injects the returned token back into the Playwright session.

### 2. Option 3: Chrome Extension Header Spoofing (Manual Fallback)
- **Goal**: Allow staff to manually solve captchas on the dashboard without Google blocking the widget.
- **Task**:
  - Build a lightweight `manifest.json` + `background.js` Chrome Extension using the `chrome.declarativeNetRequest` API.
  - The extension will intercept outgoing requests to `https://www.google.com/recaptcha/*` from the SaaS dashboard (`apptsys.samwebdevs.dpdns.org`) and rewrite the `Referer` and `Origin` HTTP headers to match the target website.
  - Staff members with the `can_solve_captcha` permission will be required to install this extension.

## How to Resume
- To test the current UI, navigate to the Dashboard -> **Live Bot Terminal** -> Click **Run Bot Now**.
- Look for the Captcha Modal to spawn. Note the red error message inside the container confirming the domain restriction block.
- When you return, state whether you'd like to build the Chrome Extension first, or wire up the NopeCha Auto-solver first!
