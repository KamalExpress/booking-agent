I agree with that decision.

If the SaaS starts making requests to CapSolver on behalf of every worker, you introduce a centralized network pattern. Even though CapSolver itself doesn't contact the target website from your VPS, centralizing the solving service can create operational drawbacks (single bottleneck, added latency, harder scaling, and a dependency on SaaS availability). Keeping the solve flow local to the worker is cleaner.

So I'd recommend a hybrid approach:

### SaaS stores the secret, worker uses it locally.

The worker authenticates itself and requests a **temporary credential**, not a permanent one.

Example:

```
POST /api/v1/worker/secrets/captcha
```

Headers:

```
Worker-ID
Timestamp
Nonce
HMAC-Signature
```

Response:

```json
{
  "provider": "capsolver",
  "api_key": "CS-xxxxxxxx",
  "ttl": 1800
}
```

The worker:

* stores it **only in memory**
* never writes it to disk
* discards it after the TTL
* automatically refreshes it when needed

---

## Add authorization rules

The endpoint should verify:

* Worker is registered
* Worker is online
* Worker is enabled
* Worker has at least one active lease (or is allowed to authenticate accounts)
* Request signature is valid
* Timestamp is within a short window (e.g. ±60 seconds)
* Nonce hasn't been seen before (prevents replay)

If any check fails:

```
403 Forbidden
```

---

## Encrypt secrets at rest

Don't store the raw CapSolver key directly in the database.

Instead:

```
Settings
    captcha_provider
    encrypted_api_key
```

Encrypt it using a master key supplied via an environment variable on the SaaS.

That way, a database dump alone doesn't expose your third-party credentials.

---

## Support multiple providers

Instead of returning just a string:

```json
{
    "provider":"capsolver",
    "api_key":"..."
}
```

return:

```json
{
    "provider":"capsolver",
    "config":{
        "api_key":"...",
        "endpoint":"https://api.capsolver.com"
    },
    "ttl":1800
}
```

Tomorrow you can switch providers without changing worker code.

---

## Version the endpoint

I'd expose it as something like:

```
GET /api/v1/worker/runtime-config
```

instead of a dedicated "captcha key" endpoint.

The response can include:

```json
{
    "captcha": {
        "provider":"capsolver",
        "api_key":"..."
    },
    "feature_flags": {
        "stealth": true,
        "headless": false
    },
    "polling": {
        "default_interval":300
    }
}
```

As your platform grows, workers will likely need more than one runtime setting. A single authenticated configuration endpoint is easier to extend than adding separate endpoints for every secret or option.

## One more recommendation

Introduce a **Secrets Manager** abstraction in the SaaS now, even if it initially reads from your settings table:

```text
SecretsManager
    ↓
Settings DB (today)

Vault / AWS Secrets Manager / Azure Key Vault (future)
```

Then the worker API never knows where the secret comes from; it just asks the `SecretsManager` for the current configuration.

This gives you a straightforward migration path if you later decide to use a dedicated secrets vault without changing the worker protocol.
