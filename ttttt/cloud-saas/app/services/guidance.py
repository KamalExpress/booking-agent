# app/services/guidance.py
# Implements the Explain, Diagnose & Recover (EDR) standard

GUIDANCE_DICT = {
    # Scheduler Decisions
    "SUCCESS": {
        "title": "Lease Successful",
        "summary": "A worker was successfully leased.",
        "why": "The scheduler found a matching task, account, and proxy.",
        "how_to_fix": [],
        "auto_recovery": "N/A",
        "severity": "Success"
    },
    "NO_READY_ACCOUNT": {
        "title": "No Account Available",
        "summary": "No portal account is currently available for this task.",
        "why": "All capable accounts are either cooling down, disabled, or leased.",
        "how_to_fix": [
            "Add new portal accounts.",
            "Enable disabled accounts.",
            "Wait for account cooldowns to expire."
        ],
        "auto_recovery": "Scheduler will retry automatically once an account leaves cooldown.",
        "severity": "Warning"
    },
    "NO_READY_PROXY": {
        "title": "No Proxy Available",
        "summary": "No proxy is currently available to pair with an account.",
        "why": "All capable proxies are either cooling down, disabled, or leased.",
        "how_to_fix": [
            "Add additional proxies.",
            "Wait for proxy cooldowns to expire.",
            "Re-enable a disabled proxy."
        ],
        "auto_recovery": "Scheduler will retry automatically once a proxy leaves cooldown.",
        "severity": "Warning"
    },
    "NO_READY_WORKER": {
        "title": "No Worker Available",
        "summary": "No worker was available to accept the task.",
        "why": "No worker with the necessary capabilities (Scrape/Book) polled the server.",
        "how_to_fix": [
            "Ensure worker instances are running.",
            "Verify workers are configured with the correct capabilities."
        ],
        "auto_recovery": "Yes, as soon as a capable worker connects.",
        "severity": "Warning"
    },
    "NO_ASSIGNMENT": {
        "title": "No Scraping Tasks",
        "summary": "No scraping tasks need to be run right now.",
        "why": "All assignments are currently leased, paused, or not yet due for polling.",
        "how_to_fix": [
            "Create a new assignment.",
            "Decrease the polling interval if faster checks are needed."
        ],
        "auto_recovery": "Yes, automatically when an assignment's polling interval is due.",
        "severity": "Info"
    },
    "NO_BOOKING_TASK": {
        "title": "No Booking Tasks",
        "summary": "No slots are available to book.",
        "why": "No slots have been found recently by the scrapers.",
        "how_to_fix": [
            "Wait for scrapers to find slots."
        ],
        "auto_recovery": "Yes, automatically triggered on a SLOT_FOUND event.",
        "severity": "Info"
    },
    "LEASE_CONFLICT": {
        "title": "Lease Conflict",
        "summary": "A stale lease update was rejected.",
        "why": "A worker attempted to update a lease that had already expired or been reassigned.",
        "how_to_fix": [
            "Check worker internet connection.",
            "Ensure worker has sufficient resources to return results before lease TTL expires."
        ],
        "auto_recovery": "The worker will automatically request a fresh lease.",
        "severity": "Warning"
    },

    # Portal Events
    "SLOT_FOUND": {
        "title": "Slot Found",
        "summary": "An available appointment slot was detected.",
        "why": "A scraper successfully checked the portal and found availability.",
        "how_to_fix": [],
        "auto_recovery": "Triggers a BookingTask.",
        "severity": "Success"
    },
    "NO_SLOTS_FOUND": {
        "title": "No Slots Found",
        "summary": "No slots were available.",
        "why": "A scraper successfully checked the portal and found no availability.",
        "how_to_fix": [],
        "auto_recovery": "N/A",
        "severity": "Info"
    },
    "LOGIN_SUCCESS": {
        "title": "Login Success",
        "summary": "Worker logged into the visa portal successfully.",
        "why": "Credentials and proxy were accepted.",
        "how_to_fix": [],
        "auto_recovery": "N/A",
        "severity": "Success"
    },
    "LOGIN_FAILED": {
        "title": "Login Failed",
        "summary": "The portal rejected the login.",
        "why": "Incorrect credentials, or the account is temporarily blocked by the portal.",
        "how_to_fix": [
            "Verify the account username and password.",
            "Log in manually to check if the account requires a password reset."
        ],
        "auto_recovery": "Account enters cooldown; will retry later.",
        "severity": "Error"
    },
    "CAPTCHA_FAILED": {
        "title": "Captcha Failed",
        "summary": "Captcha could not be bypassed.",
        "why": "CapSolver/NopeCha failed to return a valid token in time.",
        "how_to_fix": [
            "Check your captcha provider balance.",
            "Verify captcha API key configuration."
        ],
        "auto_recovery": "System will retry on the next lease.",
        "severity": "Error"
    },
    "PROXY_TIMEOUT": {
        "title": "Proxy Timeout",
        "summary": "The worker could not reach the visa portal.",
        "why": "The assigned proxy is dead, too slow, or blocked by the portal's WAF.",
        "how_to_fix": [
            "Replace the proxy if it consistently times out.",
            "Check proxy provider dashboard."
        ],
        "auto_recovery": "Proxy enters cooldown; worker gets a different proxy next time.",
        "severity": "Error"
    },
    "PORTAL_ERROR": {
        "title": "Portal Server Error",
        "summary": "The visa portal returned a server error (5xx).",
        "why": "The visa portal is undergoing maintenance or is overloaded.",
        "how_to_fix": [
            "Wait for the portal to recover."
        ],
        "auto_recovery": "System will keep trying at the configured polling interval.",
        "severity": "Warning"
    },
    "BOOKING_FAILED": {
        "title": "Booking Failed",
        "summary": "A booking attempt failed.",
        "why": "The slot was taken by someone else before completion, or a portal error occurred.",
        "how_to_fix": [
            "None (the slot is lost)."
        ],
        "auto_recovery": "Bookers will wait for the next SLOT_FOUND event.",
        "severity": "Error"
    },
    "RATE_LIMITED": {
        "title": "Rate Limited",
        "summary": "The portal rate-limited the worker (429).",
        "why": "The proxy or account made too many requests in a short time.",
        "how_to_fix": [
            "Increase your polling interval.",
            "Add more proxies/accounts to distribute load."
        ],
        "auto_recovery": "Both Account and Proxy enter cooldown.",
        "severity": "Error"
    },
    
    # Entity Statuses
    "BLOCKED": {
        "title": "Blocked",
        "summary": "This entity is blocked and cannot be used.",
        "why": "It encountered a fatal error (like a permanent ban or invalid credentials) or was manually disabled.",
        "how_to_fix": [
            "Review the logs to see the specific error.",
            "Update credentials if they are invalid.",
            "Manually unblock it from the database if you believe it is safe."
        ],
        "auto_recovery": "No. Requires manual intervention.",
        "severity": "Error"
    },
    "DISABLED": {
        "title": "Disabled",
        "summary": "This entity has been manually disabled.",
        "why": "An administrator toggled it off to prevent the scheduler from using it.",
        "how_to_fix": [
            "Re-enable it from the dashboard if you want it to be leased again."
        ],
        "auto_recovery": "No.",
        "severity": "Warning"
    },
    "COOLDOWN": {
        "title": "Cooling Down",
        "summary": "This entity is temporarily resting.",
        "why": "It was recently used or encountered a soft error (like a timeout or rate limit).",
        "how_to_fix": [
            "Wait for the cooldown period to expire."
        ],
        "auto_recovery": "Yes. It will become READY automatically when the cooldown expires.",
        "severity": "Warning"
    },
    "READY": {
        "title": "Ready",
        "summary": "This entity is ready to be used.",
        "why": "It is healthy and currently available for the scheduler.",
        "how_to_fix": [],
        "auto_recovery": "N/A",
        "severity": "Success"
    },
    "LEASED": {
        "title": "Leased",
        "summary": "This entity is currently in use.",
        "why": "The scheduler has assigned it to a worker node for a task.",
        "how_to_fix": [],
        "auto_recovery": "It will return to READY or COOLDOWN when the task finishes.",
        "severity": "Info"
    },
    "IDLE": {
        "title": "Idle",
        "summary": "This entity is idle and waiting for work.",
        "why": "It is connected and healthy, but the scheduler hasn't assigned it a task yet.",
        "how_to_fix": [],
        "auto_recovery": "N/A",
        "severity": "Success"
    },
    "WORKING": {
        "title": "Working",
        "summary": "This entity is currently executing a task.",
        "why": "It received a lease from the scheduler and is actively processing it.",
        "how_to_fix": [],
        "auto_recovery": "It will return to IDLE when the task completes.",
        "severity": "Info"
    },
    "OFFLINE": {
        "title": "Offline",
        "summary": "This entity is disconnected.",
        "why": "It missed its heartbeat check (likely crashed or lost internet connection).",
        "how_to_fix": [
            "Check the node's process logs.",
            "Restart the node."
        ],
        "auto_recovery": "It will automatically recover when it reconnects.",
        "severity": "Error"
    }
}

def get_guidance(code: str) -> dict:
    """Returns the EDR metadata for a given code. Defaults to a generic response if unknown."""
    if not code:
        code = "UNKNOWN"
    
    metadata = GUIDANCE_DICT.get(code, {
        "title": code,
        "summary": f"An event occurred with code: {code}",
        "why": "Unknown event.",
        "how_to_fix": ["Check system logs for more details."],
        "auto_recovery": "Unknown",
        "severity": "Info"
    })
    metadata["technical_code"] = code
    return metadata
