# Coding Standards & Conventions

## 1. Python / FastAPI (Control Plane)
- **Style:** Strictly adhere to PEP8 guidelines.
- **Typing:** Use strong Python typing (Pydantic models, FastAPI dependencies) for all function arguments and returns.
- **Dependencies:** Use FastAPI's `Depends()` for all dependency injection, especially around authentication (e.g., `get_ui_user`, `get_worker_user`).
- **Database:** Use SQLAlchemy for ORM and Alembic for schema migrations. No raw SQL strings.

## 2. Headless Workers (Execution Plane)
- **WAF Evasion:** **NEVER** use the standard `requests` or `httpx` libraries for external requests to Visa portals. Always use the `SessionManager` which wraps `curl_cffi` to spoof TLS fingerprints.
- **Statelessness:** Workers must never persist `capabilities` or `secrets` (like CapSolver keys) to disk. They must be loaded dynamically into memory via the `/runtime-config` endpoint.

## 3. UI / Frontend
- Vanilla CSS and HTML templates via Jinja2 are currently preferred. Keep it lightweight and maintainable.

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
