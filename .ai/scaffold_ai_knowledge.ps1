<#
.SYNOPSIS
AI Knowledge System Scaffolder
.DESCRIPTION
Run this script in the root of any new project to initialize the AI memory architecture.
#>

Write-Host "Initializing AI Knowledge System..." -ForegroundColor Green

# 1. Create Directory Structure
$directories = @(
    ".ai/permanent/architecture",
    ".ai/permanent/adr",
    ".ai/permanent/glossary",
    ".ai/permanent/standards",
    ".ai/transient/sprint",
    ".ai/transient/handoffs",
    ".ai/transient/backlog",
    ".ai/history",
    ".ai/indexes",
    ".ai/lessons",
    ".agents"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
}

# 2. Create the Master Index (.ai/README.md)
$readmeContent = @"
# AI Knowledge Base Master Index

Welcome to the canonical AI knowledge base for this project. This system is designed to minimize context loss and preserve architectural intent.

## The AI Bootstrap Read Order
If you are an AI Agent entering a fresh conversation, you **must** read the following documents in order before inspecting the source code:

1. `00-project-overview.md` (You are here: `README.md`)
2. `permanent/architecture/01-system-architecture.md`
3. `indexes/repository.md`
4. `permanent/standards/01-coding-standards.md`
5. `transient/sprint/00-current-state.md`

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
* **`lessons/`**: Operational knowledge, debugging outcomes, and failed experiments.
"@
if (-not (Test-Path ".ai/README.md")) {
    Set-Content -Path ".ai/README.md" -Value $readmeContent -Encoding UTF8
    Write-Host "Created .ai/README.md" -ForegroundColor Gray
} else {
    Write-Host ".ai/README.md already exists, skipping." -ForegroundColor Yellow
}

# 3. Create the Agent Rules (.agents/AGENTS.md)
$agentsContent = @"
# AI Workspace Instructions (AGENTS.md)

This file contains the foundational rules for all AI agents working in this repository. It is automatically injected into the context of every new conversation.

## 1. The AI Bootstrap Sequence
If you are entering a fresh conversation and do not have full context of this project, you **MUST NOT** immediately inspect the source code or reverse engineer the repository. 

Instead, you must strictly follow this read order:
1. Read `.ai/README.md` (Master Index)
2. Read `.ai/transient/sprint/00-current-state.md`
3. Read `.ai/permanent/architecture/01-system-architecture.md`
4. Read `.ai/indexes/repository.md` to map concepts to code.
5. Only then may you inspect the source code.

## 2. Documentation Ownership (Knowledge Manager)
- The documentation in `.ai/` is strictly maintained by the **Knowledge Manager** agent. 
- If you (the Developer agent) modify the architecture, database models, workflows, or APIs, you must either update the docs yourself, or delegate to the Knowledge Manager.
- Never summarize source code in documentation. Document *intent, invariants, tradeoffs, and failure modes*.
"@

if (-not (Test-Path ".agents/AGENTS.md")) {
    Set-Content -Path ".agents/AGENTS.md" -Value $agentsContent -Encoding UTF8
    Write-Host "Created .agents/AGENTS.md" -ForegroundColor Gray
} else {
    Write-Host ".agents/AGENTS.md already exists, skipping." -ForegroundColor Yellow
}

# 4. Create base templates
$templates = @(
    ".ai/permanent/architecture/01-system-architecture.md",
    ".ai/indexes/repository.md",
    ".ai/permanent/standards/01-coding-standards.md",
    ".ai/transient/sprint/00-current-state.md"
)

foreach ($file in $templates) {
    if (-not (Test-Path $file)) {
        New-Item -ItemType File -Force -Path $file | Out-Null
    }
}

Write-Host "✅ AI Knowledge System successfully scaffolded!" -ForegroundColor Green
Write-Host "Please fill in the blank template files in .ai/permanent and .ai/transient to bootstrap your new project." -ForegroundColor Yellow
