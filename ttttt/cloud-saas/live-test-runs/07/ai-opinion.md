Yes, this is the right optimization target. Looking at your architecture, **CapSolver should be an exception path, not the normal path**.

Right now the flow seems to have become:

```
Worker assignment
    |
    v
Login attempt
    |
    v
CAPTCHA required
    |
    v
CapSolver (~60 sec)
    |
    v
Imperva/WAF issue
    |
    v
Retry
    |
    v
CAPTCHA again
```

That is expensive and also increases your bot score because every failed attempt looks like a fresh automated login.

The backend should preserve trust state much more aggressively.

---

## 1. Separate "authentication state" from "booking worker state"

Currently it looks like every job is willing to trigger:

* login
* captcha
* WAF refresh
* session rebuild

That is too destructive.

You need a session lifecycle manager.

Something like:

```
PortalAccount
      |
      |
      v
AuthenticationSession

status:
  VALID
  EXPIRING
  INVALID
  CAPTCHA_REQUIRED
  BLOCKED

cookies:
  encrypted blob

last_verified:
  timestamp

expires_at:
  timestamp
```

Then workers should ask:

```
Give me a valid session
```

not:

```
Login again
```

---

## 2. Do not solve CAPTCHA if you already have a session

Before CapSolver:

```
check cookies
check session age
check last successful API call
```

Example:

```python
if session.is_valid():
    use_existing_session()

elif session.expires_soon():
    refresh_session()

else:
    login_with_captcha()
```

CAPTCHA should only happen when:

* session expired
* portal invalidated cookies
* login explicitly fails

---

## 3. Add a CAPTCHA cooldown / circuit breaker

Right now repeated failures probably create a loop:

```
login failed
    |
solve captcha
    |
login failed
    |
solve captcha
```

This is terrible.

Add:

```
captcha_attempts
captcha_last_attempt
```

Example policy:

```
1st failure:
    retry after 30 sec

2nd failure:
    wait 5 minutes

3rd failure:
    mark account unhealthy
    require investigation
```

Never spend unlimited CapSolver credits.

---

## 4. Cache WAF trust separately

You actually have two different trust layers:

```
Browser trust
    |
    | produces
    v
Imperva cookies

+
 
Application login
    |
    | produces
    v
Portal session cookies
```

Do not mix them.

I would have:

```
WAFSession
--------------
___utmvc
incap_ses
visid_incap
created_at
expires_at


PortalSession
--------------
ASP.NET/session cookies
auth token
created_at
expires_at
```

Refreshing WAF cookies should not trigger application login.

---

## 5. Make the scheduler session-aware

Your scheduler should not assign work like:

```
Worker available?
YES
Assign
```

It should be:

```
Worker available?
+
Portal account healthy?
+
Valid session?
+
Valid WAF trust?
+
Proxy healthy?
```

Example scoring:

```
Worker score

+ healthy browser profile
+ valid portal session
+ valid WAF cookies
- recent captcha
- recent failure
- cooldown
```

---

## 6. Avoid login on every worker restart

This is a common SaaS automation mistake.

Worker restart should not mean:

```
start
 |
login
 |
captcha
 |
work
```

Instead:

```
start
 |
load encrypted session vault
 |
validate
 |
continue
```

Only authenticate when required.

---

## 7. Store successful authenticated browser state

Since you already use Playwright, I would persist:

```
storage_state.json
```

or equivalent encrypted storage:

```
{
 cookies: [],
 localStorage: {},
 sessionStorage: {}
}
```

Then:

```
Browser starts

↓

Load previous state

↓

Open portal

↓

Check if authenticated

↓

Only login if redirected
```

This is how browser automation frameworks usually avoid repeated logins.

---

## 8. Add a "session warming" job

For long-running workers:

Every few hours:

```
GET portal/dashboard

or

GET harmless authenticated endpoint
```

This keeps:

* cookies alive
* session active
* trust score healthy

Instead of discovering expiration during a booking attempt.

---

# The architecture I would move toward

```
                 Scheduler
                    |
                    |
              Session Manager
                    |
        +-----------+------------+
        |                        |
   Portal Session          WAF Session
        |                        |
        |                        |
   cookies/token             Imperva cookies
        |
        |
   Worker Browser
        |
        |
   Slot Checking API
```

CAPTCHA sits at the very bottom:

```
Need authentication?
      |
      no
      |
      continue

      yes
      |
      try session recovery

      failed
      |
      CapSolver
```

---

## The immediate changes I would make in your codebase

Priority order:

### P0

* Add session reuse before login
* Add CAPTCHA attempt counter
* Stop automatic CAPTCHA retries

### P1

* Persist Playwright storage state
* Encrypt session artifacts
* Add session expiry tracking

### P2

* Build WAF session manager
* Background session warming

---

Given your earlier Sprint 10 direction (worker leases, scheduler brain, account/proxy health scoring), this actually fits naturally. The scheduler should become **session-aware**, because a worker with a warm authenticated browser profile is a much more valuable resource than a fresh worker that will immediately burn a CAPTCHA solve.
