NAV_GUIDANCE_DICT = {
    "NAV_PROXIES": {
        "title": "Step 1: Proxies",
        "summary": "To set up a slot monitor, you must first add residential or datacenter proxies.",
        "why": "Workers need proxies to bypass WAFs and avoid rate limits.",
        "severity": "Info"
    },
    "NAV_ACCOUNTS": {
        "title": "Step 2: Portal Accounts",
        "summary": "Next, add the target portal accounts (username/password) that the workers will use to log in.",
        "why": "Without accounts, the workers cannot access the secure portal to check for slots.",
        "severity": "Info"
    },
    "NAV_WORKERS": {
        "title": "Step 3: Workers",
        "summary": "Deploy headless worker nodes to your infrastructure. They will appear here once they connect.",
        "why": "Workers are the actual compute engines that execute the scraping and booking tasks.",
        "severity": "Info"
    },
    "NAV_ASSIGNMENTS": {
        "title": "Step 4: Scrapers (Tasks)",
        "summary": "Finally, create a Scraper Assignment. The scheduler will match a Worker, Proxy, and Account to execute it.",
        "why": "Assignments define WHAT you want to scrape (e.g. Visa Type, Location, Polling Interval).",
        "severity": "Info"
    },
    "NAV_BOOKING_TASKS": {
        "title": "Auto-Bookers",
        "summary": "When a Scraper finds a slot, it creates a Booking Task here automatically.",
        "severity": "Success"
    },
    "NAV_TENANTS": {
        "title": "Tenant Management",
        "summary": "Manage your SaaS customers (Tenants) and their usage limits.",
        "severity": "Info"
    },
    "NAV_LOGS": {
        "title": "Event Logs",
        "summary": "Watch real-time system events to diagnose lease conflicts, timeouts, and booking successes.",
        "severity": "Info"
    },
    "NAV_PLAYBOOK": {
        "title": "Help / Playbook",
        "summary": "View the end-to-end playbook on how to set up and monitor your distributed worker fleet.",
        "severity": "Info"
    }
}
