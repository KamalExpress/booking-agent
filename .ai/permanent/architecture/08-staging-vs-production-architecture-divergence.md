# Staging vs. Production Architectural Divergence

## 1. Architectural Invariant & Purpose
This document defines the architectural differences between the **Staging** and **Production** environments of the platform.

As mandated by **Rule 8 in `AGENTS.md`**, the system maintains a strict separation between the proven, production-grade baseline and the next-generation modular architecture:
- **Production (`feature/prod-july2026` / `feature/prod`):** Represents the proven, monolithic SaaS control plane and single-worker execution plane. Optimized for high stability, minimal schema complexity, and guaranteed notification delivery.
- **Staging (`feature/staging-july2026` / `feature/staging-aug2026`):** Contains the refactored **Execution Plane Abstraction**, **Adapter Factory**, **Multi-Provider Architecture**, **AI OCR Document Ingestion Pipeline**, and **Client Directory Management**.

---

## 2. Key Areas of Divergence

### A. Execution Plane & Worker Abstraction
| Area | Production Environment | Staging Environment |
| :--- | :--- | :--- |
| **Worker Architecture** | Monolithic `main_operator.py` containing embedded GVC portal logic directly in the class. | Decoupled `headless_booker.py` and `slot_monitor.py` utilizing the `AdapterFactory` (`core/adapters/adapter_factory.py`). |
| **Adapter Layer** | Direct HTTP session logic inside `OperatorAgent`. | Standardized `BaseAdapter` (`core/adapters/base_adapter.py`) implemented by `GVCAdapter` (`core/adapters/gvc_adapter.py`). |
| **Multi-Portal Ready** | Single-provider focus (GVC Greece). | Multi-provider architecture ready to scale across VFS, BLS, and GVC. |
| **Deployment Stack** | Single operator container (`operator-agent`). | Dual worker containers: Scraper (`slot_monitor.py`) + Dedicated Booker (`headless_booker.py`). |

### B. Database Schema & Alembic Migrations
Staging includes advanced database migrations that **have NOT been run on the production database**:
1. `014_portal_account_phone.py`: Adds phone number and secondary verification fields to `PortalAccount`.
2. `015_booking_confirmation_fields.py`: Adds booking confirmation reference, appointment letter PDF path, and verification tokens to `BookingTask`.
3. `e093ad7b8be7_execution_plane_abstraction.py`: Adds `provider_health` JSONB metrics to `PortalAccount` and `Proxy` models.

> [!CAUTION]
> **Defensive Coding Standard:**
> Because the production database lacks columns such as `provider_health`, any backend service running across or ported between environments (such as `scoring_policy.py`) **MUST NEVER** access schema-divergent properties directly (e.g. `account.provider_health`). Always use `getattr(account, 'provider_health', None)` with a safe fallback to `account.health_score`.

### C. Client Directory & AI OCR Pipeline
- **Production:** Relies on manual waitlist queue entries and standard appointment applicant fields.
- **Staging:** Includes the full **AI OCR Pipeline** (`app/services/ai_ocr_service.py`), built-in ICAO 9303 MRZ parser, client-side Tesseract.js Web Worker, and LLM text parser (`/api/v1/ocr/parse-client`) integrated into `app/templates/clients.html`.

---

## 3. Promotion & Synchronization Rules (Absolute Merge Ban)

1. **Absolute Merge Ban from Staging to Production:** Staging operates completely separately from Production. Due to fundamental structural divergence (Execution Plane Abstraction, Adapter Factory, Multi-Provider Architecture, and Staging DB migrations `014`, `015`, `e093ad7b8be7`), **NO changes from Staging may EVER be merged into Production** until the entire system architecture work, multi-portal alignment, and end-to-end booking lifecycle have been fully proven and validated on Staging, followed by explicit manual approval from the user.
2. **Production Hotfix Policy:** Any operational hotfixes needed on Production must be authored and applied surgically directly to the Production branch (`feature/prod-july2026` / `feature/prod`), strictly respecting Production's monolithic schema baseline without pulling in Staging dependencies.
3. **VPS Topology:**
   - **Production Stack (`alamiaconnect.com`):** Deployed from `feature/prod-july2026`.
   - **Staging Stack (`staging.alamiaconnect.com`):** Deployed from `feature/staging-july2026`.
   - **Scalable Architecture Stack (`scalearch.alamiaconnect.com`):** Dedicated VPS endpoint for verifying multi-portal abstractions.
4. **Selective Hotfix Backporting:** When cherry-picking bugfixes from August (e.g. WAF preflight headers, 403 backoff, `Lease` import fix) into baseline branches, only extract the targeted logic without bringing in the structural adapter refactor.
