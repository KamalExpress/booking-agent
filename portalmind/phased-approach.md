# user 
next i think we should produce the needed har files by asking the agent to open browser, login to portal and inspect dev tools; feasible? or will it burn tokens with our current setup?
# agent
Yes, it's feasible, and with your current MCP setup it shouldn't burn many tokens if you structure the task correctly.

The key is this:

Use the browser as the source of truth, not the LLM.

Don't ask the agent to "inspect the page" in a general sense. Give it a narrow research mission.

Good workflow
Launch Chrome via DevTools MCP.
Open portal.
Login (you can complete CAPTCHA/OTP manually if needed).
Enable Network capture.
Perform one workflow (search slots).
Save:
HAR
DOM snapshot
Screenshots
Console logs
Run Python locally to extract:
endpoints
payloads
headers
Save results into /knowledge.

The LLM should only read the small extracted summaries, not the raw HAR.

Bad workflow (token expensive)

"Analyze this entire webpage."

or

"Read every network request and explain them."

That causes lots of unnecessary context.

I'd define a standard "Research Mission"

For every new portal:

Discover authentication flow.
Discover API endpoints.
Discover request payloads.
Discover response schemas.
Discover selectors.
Export HAR.
Update /knowledge.
Stop.

No code generation yet.

Even better: separate phases

Phase 1: Research only (no coding)

Phase 2: Generate knowledge files

Phase 3: Generate API client

Phase 4: Generate Playwright fallback

This keeps each session focused and minimizes token usage.

I think this phased approach will give you the best balance between automation and cost. The expensive reasoning happens once during research, and afterwards the agents work mostly from your persisted knowledge base instead of rediscovering the portal each time.