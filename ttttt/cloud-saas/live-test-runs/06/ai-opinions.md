These logs are actually very useful because they invalidate the previous leading hypothesis.

## The biggest finding

This line is the smoking gun:

```text
Waiting for Imperva JS challenge to compute and set ___utmvc cookie...
___utmvc cookie not found after 15 seconds. Proceeding anyway.
Successfully refreshed 4 WAF cookies.
```

This tells us **the fix did exactly what it was supposed to do**:

* It waited.
* It actively polled.
* It never found `___utmvc`. 

So the problem is **not** "Playwright closed too early."

That hypothesis has now been tested and disproven.

---

## Even more important

Later runs don't even reach the polling stage.

Instead they fail here:

```text
Page.goto: Timeout 30000ms exceeded
waiting until "networkidle"
```

This means Playwright itself is now struggling to load the page. 

Notice how the failure evolved:

**Old behavior**

```
Playwright loads page
↓

maybe exits too early
↓

no ___utmvc
```

**New behavior**

```
Playwright can't even finish navigation
↓

networkidle timeout
↓

no ___utmvc
```

Those are very different failures.

---

# The 15-second wait is also telling us something

The log says:

```
Waiting for ___utmvc...
```

then

```
not found after 15 seconds
```

If Imperva intended to issue that cookie for this browser, 15 seconds is usually more than enough.

The fact that it never appears suggests one of:

* the JS challenge never executes
* the JS challenge executes but decides this browser isn't trusted
* Imperva no longer uses `___utmvc` for this session
* you're looking in the wrong browser context (less likely)

---

# I also noticed something else

The code waits for

```python
page.goto(..., wait_until="networkidle")
```

This is a red flag.

Modern anti-bot pages often **never become network idle**.

Analytics.

Long polling.

Beacon requests.

Heartbeat.

Challenge polling.

If the page continuously talks to the server,

```text
networkidle
```

will never occur.

Instead Playwright eventually throws

```
Timeout 30000ms exceeded
```

which is exactly what you're seeing.

---

# I would change this immediately

Instead of

```python
wait_until="networkidle"
```

I'd try

```python
wait_until="domcontentloaded"
```

or

```python
wait_until="commit"
```

Then independently poll for the cookie.

The page doesn't need to be "idle."

It only needs to execute enough JavaScript for Imperva.

---

# Another observation

Your logs now show:

```
Pre-flight navigation

↓

timeout

↓

CapSolver

↓

timeout

↓

Playwright

↓

timeout

↓

401
```

That is interesting.

The login eventually returns **401** instead of only timing out.

That means some requests are now reaching the application server instead of dying entirely inside Imperva.

That's actually progress.

---

# What I would inspect next

I think the logging now needs to become much richer.

Instead of

```
Successfully refreshed 4 cookies
```

log

```
Cookies received:

incap_ses=...
visid_incap=...
nlbi=...
___utmvc=missing
```

That single log line would answer a huge number of questions.

---

Also log

```
document.readyState

location.href

title

```

after navigation.

If Playwright reaches

```
https://pk-gr-services.gvcworld.eu/login
```

that's different from sitting on an Imperva challenge page.

---

# My current hypothesis has changed

After these logs, my ranking is now:

### 1. `networkidle` is the wrong synchronization primitive ⭐⭐⭐⭐⭐

This stands out immediately.

---

### 2. Imperva is not issuing `___utmvc` anymore ⭐⭐⭐⭐☆

Maybe because:

* browser fingerprint
* headless detection
* IP reputation
* challenge failed

---

### 3. The code assumes `___utmvc` is mandatory ⭐⭐⭐⭐☆

Verify this assumption.

Many Imperva deployments evolve over time.

Some sessions never receive that cookie anymore.

You should compare against a **real Chrome session today**.

Does Chrome still receive `___utmvc`?

If not, you're waiting for a cookie that no longer exists.

---

### 4. Browser fingerprint issue ⭐⭐⭐☆

Playwright itself may now be failing Imperva's browser validation before the JS challenge completes.

---

## My recommendation

I think it's time to stop guessing and instrument the browser itself.

After `page.goto`, capture and log:

* Current URL
* Page title
* `document.readyState`
* Every cookie (`name`, `domain`, `expires`)
* Whether `window._Incapsula_Resource` or related challenge scripts loaded (if applicable)
* A screenshot

That will tell you **what Playwright is actually seeing**. Right now the logs only tell you what it *didn't* get (`___utmvc`), not whether it's on the expected login page, stuck on an Imperva interstitial, or timing out because `networkidle` is never reached. Once you have that visibility, you'll know whether the next fix belongs in the navigation logic, the browser fingerprint, or the cookie handoff.
