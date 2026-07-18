I would avoid calling the feature **"Humane Tooltips."** It describes the tone, not what the feature actually does.

Since you're standardizing it across the entire SaaS, think of it as an **operational guidance system**, not just tooltips.

A good pattern is that every important status, error, warning, or metric has three layers:

1. **What happened?** (Plain English)
2. **Why did it happen?** (Root cause)
3. **How do I fix it?** (Recommended action)

For example:

| Code             | User sees                                                                               |
| ---------------- | --------------------------------------------------------------------------------------- |
| `NO_READY_PROXY` | **No proxy is currently available.**                                                    |
| Why?             | All scraper proxies are cooling down or disabled.                                       |
| Fix              | Add another scraper proxy, wait for cooldown to expire, or re-enable an existing proxy. |

or

| Code                   | User sees                                                                     |
| ---------------------- | ----------------------------------------------------------------------------- |
| `ACCOUNT_LOGIN_FAILED` | **The portal rejected this account's login.**                                 |
| Why?                   | The credentials may be incorrect or the account has been temporarily blocked. |
| Fix                    | Verify the username/password or wait for the account cooldown to finish.      |

This pattern works everywhere in the dashboard.

---

## I'd make it a first-class platform feature

Something like:

### Intelligent Guidance

or

### Operational Guidance

or

### Smart Help

or

### Guided Diagnostics

or

### Explain & Fix

Of these, I like **Operational Guidance** the most because it scales beyond tooltips.

Examples:

* Scheduler Decisions
* Worker Status
* Proxy Health
* Account Status
* Booking Tasks
* System Alerts
* Validation Errors
* Dashboard Metrics

can all use the exact same mechanism.

---

## I'd define a standard metadata model

Every system event should expose something like:

```yaml
title:
  No Proxy Available

summary:
  No healthy proxy was available for this worker.

technical_code:
  NO_READY_PROXY

severity:
  Warning

why:
  All scraper proxies are currently cooling down or disabled.

how_to_fix:
  - Wait until a proxy cooldown expires.
  - Add additional scraper proxies.
  - Re-enable a disabled proxy.

documentation:
  Proxy Management

auto_recovery:
  Scheduler will retry automatically in 60 seconds.
```

Notice that **tooltips become just one UI rendering** of this richer metadata.

---

## I would formalize it as a platform standard

For example:

> **Platform Standard: Explain, Diagnose & Recover (EDR)**
>
> Every significant status, warning, validation error, and system event presented in the UI must include:
>
> * **What happened?** (Human-readable summary)
> * **Why?** (Likely cause)
> * **How to fix it?** (Actionable guidance)
> * **Will the system recover automatically?** (If applicable)
> * **Learn more** (Optional documentation link)

This becomes a design rule for every dashboard page, not just Scheduler Decisions.

## My favorite name

I'd call the feature:

> **Operational Guidance**

because it's broad enough to encompass tooltips, detail panels, validation messages, health indicators, and diagnostics. Internally, each event can implement a standard **Explain → Why → Fix → Auto-Recovery** schema, giving users immediate answers instead of forcing them to interpret technical codes or search documentation. That will make the dashboard feel much more like a polished SaaS product than an engineering console.
