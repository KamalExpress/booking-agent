I like this plan. I'd approve it with a few modifications that will make it much more robust as your worker fleet grows.

---

## 1. Don't store the encrypted key in `MonitorConfig`

This is the only architectural change I'd make.

`MonitorConfig` should remain about **monitoring behavior**.

Instead create something like:

```text
SystemSetting

key
value
encrypted
updated_at
updated_by
```

or

```text
Secret

name
provider
encrypted_value
created_at
updated_at
```

Examples:

```text
captcha.capsolver.api_key

captcha.nopecha.api_key

telegram.bot_token

smtp.password
```

Otherwise `MonitorConfig` slowly becomes a dumping ground for unrelated settings.

---

## 2. Return a Runtime Configuration Version

Instead of only

```json
{
  "ttl":1800
}
```

I'd return

```json
{
    "version":"2026-07-15T12:42:00Z",
    "ttl":1800,
    ...
}
```

or

```json
{
    "config_version":17
}
```

Workers can compare versions.

If unchanged

→ keep existing config.

Very useful later.

---

## 3. Don't expose provider endpoint

Instead of

```json
"endpoint":"https://api.capsolver.com"
```

I'd simply send

```json
{
    "provider":"capsolver",
    "api_key":"..."
}
```

The endpoint belongs inside the worker implementation.

Otherwise if CapSolver changes URLs, you'll have runtime compatibility issues.

---

## 4. TTL shouldn't only apply to the key

It should apply to the **entire runtime configuration**.

Think

```text
Runtime Config

captcha

feature flags

timeouts

polling defaults

future OCR config

future proxy config
```

One cache.

One TTL.

---

## 5. Add a Configuration Hash

This is one of my favorite patterns.

Example

```json
{
    "config_hash":"a93c21..."
}
```

Worker sends

```text
If-Config-Hash: a93c21...
```

Server responds

```text
304 Not Modified
```

No JSON payload.

Very efficient if you eventually have 50-100 workers.

---

## 6. Encrypt before writing to DB

The UI should never receive encrypted values.

Flow should be

```text
Admin

↓

HTTPS

↓

Backend

↓

SecretsManager.encrypt()

↓

Database
```

When editing settings

never return

```text
***************
```

or encrypted blobs.

Instead

```text
Configured ✓
```

with a Replace button.

Same UX AWS uses.

---

## 7. Add Secret Metadata

I would store

```text
Provider

Updated By

Updated At

Rotation Count
```

Very useful for audits.

---

## 8. Worker shouldn't request config every startup

I'd do

```text
Startup

↓

Fetch config

↓

Memory cache

↓

Refresh every TTL

↓

Immediate refresh after 401/403 if needed
```

Don't hit the endpoint unnecessarily.

---

## 9. Future-proof Runtime Config

I'd actually define it now.

Something like

```json
{
  "version":17,
  "ttl":1800,

  "captcha":{
      "provider":"capsolver",
      "api_key":"..."
  },

  "worker":{
      "max_parallel_logins":2,
      "heartbeat":30
  },

  "features":{
      "stealth":true,
      "ocr":false
  }
}
```

This becomes the single source of truth.

---

## 10. The Fernet key

Regarding the agent's question:

> Should I generate a static 32-byte Fernet key and place it in `.env`?

**Yes.**

But:

* never commit it
* generate it once
* keep it backed up
* treat it like your JWT secret

If you lose it,

you lose the ability to decrypt every stored secret.

---

# My only requested architectural change

Instead of

```
MonitorConfig

captcha_provider

encrypted_api_key
```

I'd reply to the agent with:

> Create a dedicated `SecretsManager` backed by a generic `SystemSetting`/`Secret` store rather than putting encrypted credentials inside `MonitorConfig`. Runtime configuration should remain operational configuration, while secrets should live in a dedicated abstraction. The worker protocol can remain exactly as proposed.

Everything else in the plan is solid and aligns well with the distributed architecture you've been moving toward.
