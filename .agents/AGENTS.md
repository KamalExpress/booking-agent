# AI Workspace Instructions (AGENTS.md)

This file contains the foundational rules for all AI agents working in this repository. It is automatically injected into the context of every new conversation.

## 1. The AI Bootstrap Sequence
If you are entering a fresh conversation and do not have full context of this project, you **MUST NOT** immediately inspect the source code or reverse engineer the repository. 

Instead, you must strictly follow this read order:
1. Read `.ai/README.md` (Master Index)
2. Read `.ai/transient/sprint/04-current-state.md` (or equivalent current sprint handoff)
3. Read `.ai/permanent/architecture/01-system-architecture.md`
4. Read `.ai/indexes/repository.md` to map concepts to code.
5. Only then may you inspect the source code.

## 2. Project Purpose
This project is a multi-tenant SaaS application that coordinates distributed headless workers to scrape and book visa appointments automatically. It consists of a FastAPI backend (Control Plane) and headless Python workers (Execution Plane).

## 3. Coding Standards & Principles
- **FastAPI / Python:** Follow PEP8. Use strong typing. 
- **WAF Evasion:** Headless workers use `curl_cffi` to mimic real browser TLS fingerprints and bypass Imperva/Cloudflare. Do not replace this with standard `requests`.
- **Database:** PostgreSQL managed via SQLAlchemy and Alembic.

## 4. Documentation Ownership (Knowledge Manager)
- The documentation in `.ai/` is strictly maintained by the **Knowledge Manager** agent. 
- If you (the Developer agent) modify the architecture, database models, workflows, or APIs, you must either update the docs yourself following the strict `Knowledge Coverage` templates, or delegate to the Knowledge Manager.
- Never summarize source code in documentation. Document *intent, invariants, tradeoffs, and failure modes*.

## 5. PortalMind Workflow Rules
**If a WAF (Imperva, Cloudflare, Akamai, DataDome, PerimeterX, etc.) is detected, immediately switch to "Manual Browser Research Mode". Do not attempt repeated automated bypasses. Request a user-captured HAR or attach to an already authenticated Chrome session via the Chrome DevTools MCP or Antigravity Browser Control.**

### Research Priority Order
1. **Chrome DevTools MCP / Antigravity Browser** (attached to user's authenticated browser)
2. **User-provided HAR**
3. **Playwright** (for automation generation and testing only, not for research)
4. **Headless Playwright** (only when no WAF exists)

## 6. Handoff & Sprint Planning Rules
When taking over a session via a handoff document (e.g., in `.ai/transient/handoffs/`), you MUST strictly adopt the 'Pending Work / Next Session Objectives' listed in that document as the definitive scope for your sprint.
- DO NOT invent or assume new features.
- Address the exact architectural gaps specified (e.g., if the handoff specifies "Dual Pools", you must design Dual Pools).
- If the handoff is unclear, explicitly ask the user for clarification before drifting out of scope.

## 7. Operational Guidance & Terminology
Whenever a new operational event, technical term, scheduling decision, or error code is introduced to the system, you **MUST** update the `.ai/permanent/architecture/06-operational-guidance-glossary.md` file. All new events must conform to the **Explain, Diagnose & Recover (EDR)** standard.

---
*Always mirror sprint planning artifacts to `.ai/transient/handoffs/` when closing out a sprint.*

## 8. Deployment & Migrations Constraints
- **Local Environment:** The user develops on a low-end laptop without Docker installed.
- **Agent Constraint:** Agents **MUST NOT** attempt to run `alembic` migrations or `docker-compose` commands locally (unless specifically authorized). 
- **Production Pipeline:** Database migrations and docker builds are automatically handled via Portainer on the VPS (staging/production) utilizing the configurations in the `vps-setup` directory.

## 9. Testing & Deployment Tooling
- **E2E Testing:** Playwright tests are located in `testing-procedure/keagent-e2e-tests/`. Run them via `npx playwright test` to verify workflows.
- **Portainer CDP Automation:** The staging deployment is automated to bypass Cloudflare and WAFs. 
  - To deploy changes to the staging environment, switch to the `devops-agent` directory and run `npm run deploy:staging`. 
  - This script connects via CDP (Chrome DevTools Protocol) to an already running instance of Google Chrome opened by the user with the flag `--remote-debugging-port=9222`. It requires the user to have Chrome open and authenticated to Portainer.

## 10. GVC Appointment Types
When building UI or filling Queue Management data, strictly use the following GVC appointment type codes:
- `0`: Submission Schengen Visa (Short term – Type C)
- `2`: National visa (Long term - type D)
- `5`: Premium Lounge (optional service at an additional charge)
- `6`: Prime Time (optional service at an additional charge)
- `26`: Long-Term Type D (Seasonal/Dependent Employment) - *(Default)*