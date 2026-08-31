# AI Workspace Instructions (AGENTS.md)

This file contains the foundational rules for all AI agents working in this repository. It is automatically injected into the context of every new conversation.

## 0. critical instructions BEFORE ANY ANALYSIS:

1. Read .repobrain/knowledge_graph.md
2. Read .repobrain/conventions.md
3. If task concerns architecture, use RepoBrain search first.
4. Do NOT inspect repository manually until RepoBrain has been consulted.

If you start exploring files without RepoBrain,
STOP immediately and restart the task.

At the beginning of EVERY task output:

RepoBrain Checklist

[ ] conventions.md loaded
[ ] knowledge_graph.md loaded
[ ] searched RepoBrain
[ ] only then inspected source files

Paste the exact RepoBrain command you ran."
"Show the first 20 lines of RepoBrain output."
"What symbols did RepoBrain return?"
"What knowledge graph nodes were traversed?"

## 1. The AI Bootstrap Sequence
If you are entering a fresh conversation and do not have full context of this project, you **MUST NOT** immediately inspect the source code or reverse engineer the repository. 

Instead, you must strictly follow this read order:
1. Read `.ai/README.md` (Master Index)
2. Read `.ai/transient/sprint/04-current-state.md` (or equivalent current sprint handoff)
3. Read `.ai/permanent/architecture/01-system-architecture.md`
4. Read `.ai/indexes/repository.md` to map concepts to code. 
   - *Note:* Check `.ai/repobrain_status.md` to verify RepoBrain's index status. If RepoBrain artifacts exist in the `.repobrain/` directory within the module you are working on (e.g., `ttttt/cloud-saas/.repobrain/` or `ttttt/operator-agent/.repobrain/`), query its generated `conventions.md` and `knowledge_graph.md` for fast symbol navigation.
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

## 8. Deployment & Architecture Isolation Constraints (Strict Staging / Production Separation)
- **Architectural Divergence & Merge Ban:** Staging operates completely separately and independently from Production. Due to fundamental structural divergence (Execution Plane Abstraction, Adapter Factory, Multi-Provider Architecture, and Staging DB migrations `014`, `015`, `e093ad7b8be7`), **NO changes from staging may EVER be merged into production** until the entire system architecture work, multi-portal alignment, and end-to-end booking lifecycle have been fully proven and validated on staging, followed by explicit manual approval from the user.
- **Auto-Booking / Execution Code:** Any changes related to auto-booking (the execution plane) MUST be kept strictly on `staging`. They MUST pass manual verification before pushing to production. NEVER merge or push to production unless 100% confident.
- **Production Hotfix Policy:** Any emergency hotfixes required for Production must be applied surgically and directly to the Production branch (`feature/prod-july2026` / `feature/prod`), strictly respecting Production's monolithic schema baseline without pulling in Staging dependencies.
- **Scalable Architecture Branch:** The `feature/scalable-arch` branch MUST be deployed to a completely separate endpoint on the VPS (`scalearch.alamiaconnect.com`). It MUST remain separate from both `staging` and `production` until the new architecture handles at least two portals successfully. Only after successful verification across multiple portals can it be merged into `staging`, and only after explicit manual approval can it go to `production`.
- **Machine Awareness:** Agents MUST check the `Device name` in their User Context metadata or via hostname.
- **High-End Local Dev (`DESKTOP-5E6DM1M`):** On this specific machine, agents are AUTHORIZED and ENCOURAGED to run local Docker Compose stacks, execute `alembic` migrations, and build containers locally.
  - **SaaS Backend:** `ttttt/cloud-saas/docker-compose.yml`
  - **Operator Agent:** `ttttt/operator-agent/docker-compose.local.yml`
- **Low-End/Other Machines:** On all other machines, the user develops without Docker. Agents **MUST NOT** attempt to run `alembic` migrations or `docker-compose` locally. 
- **Production Pipeline:** Database migrations and docker builds are automatically handled via Portainer on the VPS (staging/production) utilizing the configurations in the `vps-setup` directory.

## 9. Testing & Deployment Tooling
- **E2E Testing:** Playwright tests are located in `testing-procedure/keagent-e2e-tests/`. When adding new E2E tests, write them as `.spec.js` files inside the `testing-procedure/keagent-e2e-tests/tests/` directory. Run them via `npx playwright test` to verify workflows.
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

## 11. RepoBrain Optimization Engine
RepoBrain is an AI context optimization engine that runs via Docker (`scripts\update_repobrain.ps1`) to maintain the workspace knowledge graphs.
- **Do not run the refresh script at the start of every session.** It is resource intensive.
- Always check `.ai/repobrain_status.md` to verify the last time it was executed.
- Only run an incremental refresh (`scripts\update_repobrain.ps1`) if significant architectural changes or documentation updates have occurred since the last logged run.

## 12. Alamia TOS MCP Server (AI Internal Tooling)
The Cloud SaaS exposes a native FastMCP server (`ttttt/cloud-saas/app/mcp_server.py`) mounted at `/mcp` over SSE on the `feature/alamia-tos-mcp` branch (`https://keagent-staging.alamiaconnect.com/mcp/sse`).
- **Primary Tools:** `get_workers()`, `create_mock_worker()`, `fetch_agent_monitor_logs()`.
- **Usage Rule:** Agents should utilize these MCP tools for real-time telemetry inspection, worker capability audits, and end-to-end lease verification during development and debugging sessions.
- **Architecture Reference:** Consult `.ai/permanent/architecture/10-mcp-server-integration.md` for tool specifications and connection instructions.