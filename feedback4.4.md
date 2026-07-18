
For a SaaS dashboard like Kamal Express, I wouldn't think of this as a **tooltip problem**. I'd think of it as a **contextual help system**.

A simple tooltip library like Tippy.js is excellent for short hints ("Copy to clipboard", "Last checked 5 minutes ago"), but it's not ideal for:

* What happened
* Why it happened
* How to fix it
* Auto-recovery status
* Links to documentation

That's too much information for a hover popup.

## My recommendation

Use **Floating UI** as the positioning engine and build your own reusable "Guidance Popover" component.

**Why Floating UI?**

* Modern successor to Popper.js
* Extremely flexible positioning
* Supports hover, click, focus, touch
* Great accessibility
* Doesn't impose any styling
* Lets you build rich interactive popovers instead of tiny tooltips

You can create a reusable component like:

```
┌────────────────────────────────────────────┐
⚠ No healthy proxy available

All scraper proxies are currently cooling
down or disabled.

Why?
• Every configured scraper proxy is either
  cooling down or marked unavailable.

How to fix
✓ Wait for cooldown expiry
✓ Add another scraper proxy
✓ Re-enable a disabled proxy

System
Scheduler will retry automatically in 60 sec.

[Open Proxy Manager]
└────────────────────────────────────────────┘
```

This is far more useful than a one-line tooltip.

---

## I'd use three UI levels

### Level 1 — Tooltip

Tiny hints.

```
ⓘ Last heartbeat received 18 seconds ago
```

---

### Level 2 — Guidance Popover ⭐

This should become your standard.

Activated by:

* clicking an icon
* hovering a status badge
* clicking an error badge

Contains:

* title
* explanation
* why
* fix
* auto recovery
* button

---

### Level 3 — Details Drawer

For complicated situations.

Example:

```
Scheduler Decision

Selected Worker
Selected Account
Selected Proxy
Scheduler Score

Timeline

Cooldown History

Recent Failures

Recommendations
```

Instead of a tooltip, clicking "Details" opens a side drawer.

---

## Libraries I'd use

### ⭐ Floating UI (9.5/10)

Best choice.

Pros

* modern
* actively maintained
* accessible
* very flexible
* supports rich content

Cons

* you build the component

---

### Radix UI (9.5/10)

If you're already using React.

Provides

* Tooltip
* Popover
* Hover Card
* Dialog

Excellent accessibility.

---

### shadcn/ui (10/10)

If you're using React + Tailwind.

This would actually be my favorite.

It already has

* Tooltip
* Popover
* Hover Card
* Sheet
* Dialog

all styled nicely.

---

### Tippy.js (7.5/10)

Still good.

I'd use it only for

```
ⓘ
```

style hints.

Not for diagnostics.

---

### Shepherd.js

Great for onboarding tours.

Not relevant here.

---

## I would even define a reusable component

Instead of "Tooltip", create a component called:

```
<OperationalGuidance />
```

Usage:

```html
<OperationalGuidance
    code="NO_READY_PROXY"
/>
```

Internally it renders

```
Title

Description

Why

Fix

Auto Recovery

Learn More
```

The UI doesn't need to know anything else.

Every screen uses the same component.

---

## Architecture I'd recommend

```
Backend

Event
↓

Guidance Metadata

↓

Frontend

OperationalGuidance Component

↓

Floating UI Popover

↓

User
```

This way, the backend provides structured guidance metadata, and the frontend consistently renders it across Scheduler Decisions, Worker Health, Proxy Status, Account Issues, Booking Tasks, and system alerts.

For a production SaaS, this approach will age much better than sprinkling Tippy.js tooltips throughout the application.
