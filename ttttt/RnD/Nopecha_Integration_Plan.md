# NopeCha Integration Plan

We can successfully use NopeCha to solve the CAPTCHAs automatically. Based on the `RnD/NopeCha.md` documentation, NopeCha supports solving reCAPTCHA tokens entirely in the background via API calls.

## What is Needed

To implement this, we need the following:

1. **NopeCha API Key:** You will need to obtain your API key from NopeCha and add it to your `.env` file (e.g., `NOPECHA_API_KEY=your_key_here`).
2. **Website Sitekey:** We need the exact reCAPTCHA `sitekey` used by `https://pk-gr-services.gvcworld.eu/`. This is a public key embedded in their login and booking pages. 

## Open Questions

> [!WARNING]
> **Sitekey:** Do you already have the `sitekey` from the target website? If not, I can write a quick script to fetch the login page and extract it automatically, or you can find it by inspecting the page source (look for `data-sitekey` or `grecaptcha.execute('sitekey')`).
> 
> **Integration Method:** We can either install the official `nopecha` Python package (`pip install nopecha`), or use the minimal dependency approach using the `requests` library we already have installed. I recommend the `requests` approach to keep dependencies minimal. Which do you prefer?

## Proposed Changes

### [MODIFY] [operator.py](file:///f:/Playgrounds/bookingbot/ttttt/operator.py)
We will update the `solve_captcha` method to:
1. Send a POST request to `https://api.nopecha.com/token` with the target `sitekey`, `url`, and our `NOPECHA_API_KEY`.
2. Retrieve the `job_id` from the response.
3. Poll the `https://api.nopecha.com/token` GET endpoint every few seconds using the `job_id` until the solved token is returned.
4. Inject this solved token into the `login` and `book_appointment` payloads.

### [MODIFY] [.env.example](file:///f:/Playgrounds/bookingbot/ttttt/.env.example)
Add `NOPECHA_API_KEY` and `TARGET_SITEKEY` placeholders.

## Verification Plan
We will dry-run the `operator.py` script. The Agent will attempt to log in; we will observe the logs to verify that NopeCha accepts the job, solves the CAPTCHA, and that the website accepts the resulting token (meaning the 401 Unauthorized should hopefully become a 200 OK).
