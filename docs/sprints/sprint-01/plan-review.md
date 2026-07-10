Overall: **9.5/10**. I would approve it with a few refinements before any code is written.

### Changes I'd make

1. **Split `knowledge/` into raw and derived**

```
knowledge/
    raw/
        endpoints.json
        requests.json
        responses.json
        headers.json

    derived/
        workflow.json
        auth.json
        selectors.json
        portal_profile.json
```

Never overwrite the raw extracted data.

---

2. **Add `portal_profile.json`**

Every portal should have a single summary:

```json
{
  "framework": "jQuery",
  "auth": "Cookie",
  "captcha": "Cloudflare Turnstile",
  "api_style": "REST",
  "base_url": "...",
  "csrf": true,
  "websocket": false
}
```

This becomes the first file every future agent reads.

---

3. **Expand `analyze_har.py`**

Don't stop at endpoints.

Extract:

* endpoints
* methods
* request schemas
* response schemas
* cookies
* auth headers
* CSRF tokens
* content types
* timing
* duplicate requests

---

4. **Add `analyze_dom.py`**

Using Playwright:

* selectors
* forms
* buttons
* hidden inputs
* iframes
* CAPTCHA detection

This keeps DOM extraction separate from HAR analysis.

---

5. **Add a `compare_har.py` now**

Future portal updates become trivial.

```
old.har
↓

new.har
↓

Report:
+ endpoint changed
+ header changed
+ payload changed
```

---

6. **Verification**

Instead of only:

> Verify extraction.

Add:

```
Verify that no LLM ever reads a raw HAR larger than X MB.

All analysis must come from extracted JSON.
```

That enforces your token-saving objective.

---

### One more phase

I'd insert a **Phase 2.5**:

```
Research
↓

Knowledge

↓

Knowledge Validation   ← new

↓

API Client

↓

Playwright
```

During validation, the agent confirms every endpoint and selector against a live session before generating code. That prevents building automation on stale or incorrect assumptions.

---

## Final verdict

I would **approve this plan**. The only structural additions I'd insist on are:

* `portal_profile.json`
* `analyze_dom.py`
* `compare_har.py`
* Separate `knowledge/raw` and `knowledge/derived`

Those additions will make PortalMind much more maintainable as you start supporting multiple portals and dealing with changes over time.
