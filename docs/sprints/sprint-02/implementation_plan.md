# PortalMind: Level 3 Architecture (Behavior Analysis)

This implementation plan outlines the shift from Level 2 (Knowledge Graph) to **Level 3 (Behavior Analysis)**. The goal is to move beyond HTTP parsing into true web application behavior modeling by introducing a clear separation between **Analyzers** (which populate the graph) and **Reasoners** (which infer behavior from the graph), as well as adding the foundation for Level 4 (Planning).

## User Review Required

> [!NOTE]
> The architectural tweaks (DataFlowReasoner, Confidence/Provenance, Planner) have been applied. Please verify the finalized Level 3 Architecture.

## Proposed Architecture

We will introduce a new `reasoners/` layer to process the Knowledge Graph, update the core graph models to support tracking, and introduce a `planners/` boundary.

### 1. New Reasoner Layer

#### [NEW] [portalmind/reasoners/](file:///f:/Playgrounds/bookingbot/portalmind/reasoners/)
Reasoners traverse the `KnowledgeGraph` to infer new, higher-level facts and state machines. They never read raw HARs directly.

#### [NEW] [portalmind/reasoners/dataflow.py](file:///f:/Playgrounds/bookingbot/portalmind/reasoners/dataflow.py)
**DataFlow Reasoner:**
- Traverses all endpoints and schemas in the graph.
- Discovers variable provenance using configurable extractors (headers, cookies, JSON, forms, query params).
- Supports exact matches and configurable heuristics to build a generalized dependency graph (`PRODUCES`, `CONSUMES`) for IDs, pagination cursors, tokens, and CSRF.

#### [NEW] [portalmind/reasoners/workflow.py](file:///f:/Playgrounds/bookingbot/portalmind/reasoners/workflow.py)
**Workflow Reasoner:**
- Synthesizes a state machine (`State` nodes, `TRANSITION` edges).
- Infers application states from observable changes in navigation, DOM, cookies, redirects, response characteristics, and variable production/consumption (not just authentication).

### 2. Graph Model Enhancements

#### [MODIFY] [portalmind/models/graph.py](file:///f:/Playgrounds/bookingbot/portalmind/models/graph.py)
- **Confidence Scores:** Every node and edge will include a `confidence` float property (e.g., `0.94`).
- **Provenance Tracking:** Every node and edge will include provenance metadata: `created_by` (e.g., "DataFlowReasoner"), `artifact` (e.g., "synthetic.har"), and `evidence` (a list of source nodes/requests).

### 3. The Planner Boundary

#### [NEW] [portalmind/planners/](file:///f:/Playgrounds/bookingbot/portalmind/planners/)
- Introduce a placeholder `AutomationPlanner` interface.
- Establishes the pipeline boundary: `Knowledge Graph -> Reasoners -> Planner -> Automation Generator`.
- Even if empty today, it ensures the architecture is ready for Level 4.

### 4. Storage Evolution

#### [NEW] [portalmind/storage/sqlite.py](file:///f:/Playgrounds/bookingbot/portalmind/storage/sqlite.py)
- A relational backend for the Knowledge Graph to allow complex querying.

#### [MODIFY] [portalmind/storage/__init__.py](file:///f:/Playgrounds/bookingbot/portalmind/storage/__init__.py)
- Establish an abstract `StorageBackend` base class so the CLI can swap between JSON and SQLite seamlessly.

### 5. CLI Updates

#### [MODIFY] [portalmind/cli.py](file:///f:/Playgrounds/bookingbot/portalmind/cli.py)
- Update the `ingest` pipeline: `Artifact -> Ingestor -> Normalizer -> Analyzers -> Graph -> Reasoners -> Storage -> Export`.

## Verification Plan

### Automated Tests
- We will expand `test_pipeline.py` using the `synthetic.har` fixture.
- Assert that `Node` and `Edge` objects correctly persist `confidence` and `provenance` metadata.
- Assert that the `DataFlowReasoner` correctly identifies the overlapping `"abc"` token, creates a `Variable` node, and tracks the `evidence` leading to its creation.

### Execution against Example Fixture
- Run `portalmind ingest har portalmind/har/login-data-entry-search-slots.txt`.
- **Strict Requirement**: Verify that the framework builds the behavior graph without inspecting, summarizing, or generating any target-specific automation code based on the fixture.
