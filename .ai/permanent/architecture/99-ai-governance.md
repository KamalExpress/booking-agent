# AI Governance (The Constitution)

## Principles

1. **Understand Before Implementing:** AI must always understand the architecture before writing code.
2. **Architecture Takes Precedence:** Architecture takes precedence over implementation details.
3. **Intent over Implementation:** Documentation explains intent, tradeoffs, and invariants—not the source code line-by-line.
4. **Single Source of Truth:** Knowledge must have a single source of truth. Avoid duplicate documentation.
5. **Incremental Updates:** Prefer incremental updates to documentation when changes are made.
6. **Record Decisions:** Record architectural decisions as ADRs.
7. **Capture Lessons:** Record engineering lessons (failures, discoveries, debugging outcomes) in `.ai/lessons/`.
8. **Generated vs Curated:** Generated artifacts (like dependency maps) are never edited manually. Curated knowledge is maintained strictly by the Knowledge Manager.
9. **Bootstrap Sequence:** Fresh conversations always follow the bootstrap sequence outlined in `AGENTS.md`.
10. **Architecture Drift:** Architecture changes require ADR and System Architecture updates *before* writing code.
11. **Conflict Resolution:** If documentation conflicts with code, investigate the discrepancy rather than overwriting blindly.

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
