# Sprint 04: Automation Planning (Level 4)

In Sprint 04, PortalMind transitions from a "Digital Twin" of the web application into an intelligent automation planner. Crucially, we will **not** generate executable code (Python/Playwright) in this sprint. Instead, we will build a dedicated Planning layer that emits an abstract execution plan using a generic Automation Domain-Specific Language (DSL). 

This approach decouples "what to do" from "how to execute it," ensuring robustness and preventing vendor lock-in.

## User Review Required

> [!IMPORTANT]
> The architectural roadmap has shifted. We are introducing the `planners/` module with distinct roles (Goal, Execution, Strategy, Readiness) and a new `models/dsl.py`. Please review the boundaries to ensure they match your expectations.

## Proposed Architecture

### 1. The Automation DSL

#### [NEW] [portalmind/models/dsl.py](file:///f:/Playgrounds/bookingbot/portalmind/models/dsl.py)
A structured representation of an automation script, independent of any language or runtime.
- `AutomationPlan`: The root model containing the goal, required variables, preconditions, and a list of generic steps.
- `Step`: An abstract instruction (e.g., `browser.goto`, `api.request`, `wait.until`, `decision.retry`).
- `Strategy`: Enum indicating whether a step should be executed via `API`, `BROWSER`, or `HYBRID`.

### 2. The Planning Modules

#### [NEW] [portalmind/planners/goal.py](file:///f:/Playgrounds/bookingbot/portalmind/planners/goal.py)
**Goal Planner:**
- Input: A high-level target (e.g., "Book an appointment").
- Output: The `Required States`, `Required Variables`, `Preconditions`, and `Success Criteria` necessary to achieve the target, inferred from the Knowledge Graph.

#### [NEW] [portalmind/planners/strategy.py](file:///f:/Playgrounds/bookingbot/portalmind/planners/strategy.py)
**Strategy Planner:**
- For each step in the goal path, intelligently decides the optimal execution strategy:
  - `API`: Fast, headless, lightweight (e.g., fetching a JSON payload).
  - `BROWSER`: Necessary for complex UI interactions, CAPTCHA, or heavy JS logic.
  - `HYBRID`: Mixing both.

#### [NEW] [portalmind/planners/execution.py](file:///f:/Playgrounds/bookingbot/portalmind/planners/execution.py)
**Execution Planner:**
- Consumes the Goal and the Strategy.
- Outputs an `AutomationPlan` (using the DSL) that represents a state machine / BPMN flow. It injects `Decision`, `Retry`, `Timeout`, and `Alternative` nodes.

#### [MODIFY] [portalmind/planners/readiness.py](file:///f:/Playgrounds/bookingbot/portalmind/planners/readiness.py) *(formerly automation.py)*
**Readiness Analyzer:**
- Acts as the final gatekeeper before code generation (or simulation).
- Evaluates the generated `AutomationPlan` against the `KnowledgeGraph`.
- If required endpoints, selectors, or data flows are missing, it halts and reports exactly what artifact is needed to bridge the gap.

### 3. Pipeline Updates

#### [MODIFY] [portalmind/cli/__main__.py](file:///f:/Playgrounds/bookingbot/portalmind/cli/__main__.py)
- Introduce a new command: `portalmind plan "Book an appointment"`.
- This command reads an exported Knowledge Graph from disk, runs the Planners, and outputs the resulting DSL to `plan.yaml`.
- The output halts at the Readiness stage, either producing `plan.yaml` (if ready) or `missing_artifacts.json` (if blocked).

## Verification Plan

### Automated Tests
- We will mock a `KnowledgeGraph` populated with endpoints and variables for a simple flow (e.g., Login -> Fetch Profile).
- Assert that the `GoalPlanner` identifies the auth token dependency.
- Assert that the `StrategyPlanner` assigns the `API` strategy to "Fetch Profile" but perhaps `BROWSER` to "Login" (simulating a complex auth gate).
- Assert that the `ReadinessAnalyzer` fails the plan if we intentionally omit the "Login" endpoint from the graph.
