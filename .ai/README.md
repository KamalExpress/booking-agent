# AI Knowledge Base Master Index

Welcome to the canonical AI knowledge base for this project. This system is designed to minimize context loss and preserve architectural intent.

## The AI Bootstrap Read Order
If you are an AI Agent entering a fresh conversation, you **must** read the following documents in order before inspecting the source code:

1. `00-project-overview.md` (You are here: `README.md`)
2. `permanent/architecture/01-system-architecture.md`
3. `permanent/architecture/02-database.md`
4. `permanent/architecture/03-network-layer.md`
5. `permanent/architecture/04-worker-management.md`
6. `permanent/architecture/05-secrets-management.md`
7. `permanent/standards/03-coding-standards.md`
8. `transient/sprint/04-current-state.md`

---

## Directory Structure

### Permanent Knowledge (Lives for Years)
* **`permanent/architecture/`**: High-level design intent, tradeoffs, and system boundaries.
* **`permanent/adr/`**: Architecture Decision Records. Contains the `README.md` index of all accepted, rejected, and deprecated decisions.
* **`permanent/glossary/`**: The single source of truth for project terminology.
* **`permanent/standards/`**: Coding conventions and testing standards.

### Transient Knowledge (Lives for Days)
* **`transient/sprint/`**: The current sprint's focus and objectives.
* **`transient/handoffs/`**: Session handoffs summarizing the immediate delta between chats.
* **`transient/backlog/`**: Pending tasks.
* **`transient/repository-health.md`**: Tracking architecture drift, documentation coverage, and missing docs.

### History & Meta
* **`history/`**: Architecture timeline. Records additions, removals, and deprecations sprint-by-sprint.
* **`indexes/`**: 
  * `repository.md`: Maps high-level concepts to source code directories and ADRs.
  * `dependency-map.md`: Mermaid graph of system components.
* **`lessons/`**: Operational knowledge, debugging outcomes, failed experiments, and WAF bypass strategies.

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
