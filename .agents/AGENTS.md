## PortalMind Workflow Rules

**If a WAF (Imperva, Cloudflare, Akamai, DataDome, PerimeterX, etc.) is detected, immediately switch to "Manual Browser Research Mode". Do not attempt repeated automated bypasses. Request a user-captured HAR or attach to an already authenticated Chrome session via the Chrome DevTools MCP or Antigravity Browser Control.**

### Research Priority Order
1. **Chrome DevTools MCP / Antigravity Browser** (attached to user's authenticated browser)
2. **User-provided HAR**
3. **Playwright** (for automation generation and testing only, not for research)
4. **Headless Playwright** (only when no WAF exists)
