# Secrets Management Architecture

## Purpose
To securely distribute sensitive credentials (e.g., CapSolver keys, Proxy credentials) to distributed headless workers without hardcoding them in the worker codebase or storing them persistently on the worker nodes.

## Responsibilities
- Serve a centralized `runtime-config` payload to authenticated workers.
- Encrypt API keys at rest in the SaaS PostgreSQL database.
- Rotate or invalidate credentials instantly across the fleet from the SaaS dashboard.

## Public Interfaces
- `GET /api/worker/runtime-config` (Or a POST with HMAC signature).

## Dependencies
- Settings DB (Currently stores the encrypted master API keys).
- Worker Node Memory (Temporarily caches the credentials).

## Invariants
- Workers **must never** write the CapSolver or Proxy keys to disk. They must be kept entirely in memory and discarded upon exit or TTL expiry.
- The SaaS must return configuration dynamically (e.g., `{"provider": "capsolver", "api_key": "CS-xxx"}`) so that switching providers does not require updating worker source code.

## Failure Modes
- **SaaS Unavailable:** Workers will fail to fetch their `runtime-config` on boot and will enter a retry loop until the SaaS is reachable.

## Extension Points
- The `SecretsManager` abstraction on the SaaS can eventually be swapped out from reading the Postgres Settings table to integrating with AWS Secrets Manager or HashiCorp Vault.

## Related Source Directories
- `ttttt/operator-agent/core/config.py` (Hypothetical worker-side config loader)

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
