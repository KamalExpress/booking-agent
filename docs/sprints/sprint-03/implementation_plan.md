# Sprint 03: Multi-Artifact Correlation Engine (Level 3+)

In this sprint, we elevate the ingestion framework to support multi-artifact correlation by introducing a global Timeline, a Correlation Engine, and robust formal models for Artifacts. This represents the final major capability needed before transitioning to Level 4 (Automation Planning).

## Architectural Principles

> **Every module should answer exactly one question.**
> - **Ingestors** → "What artifacts exist?"
> - **Normalizers** → "How do we represent them uniformly?"
> - **Analyzers** → "What facts can be extracted?"
> - **Reasoners** → "What behavior can be inferred?"
> - **Planner** → "What sequence of actions achieves a goal?"
> - **Generator** → "How do we implement that plan?"
> - **Runtime** → "How do we execute and monitor it?"

## User Review Required

> [!NOTE]
> Review the refined architecture below. It introduces the `Timeline` model, formalizes `Artifact` inheritance, and separates correlation logic into a generic `CorrelationEngine`.

## Proposed Architecture

### 1. Formal Artifact Models

#### [NEW] [portalmind/models/artifact.py](file:///f:/Playgrounds/bookingbot/portalmind/models/artifact.py)
We will formalize the concept of Artifacts:
- `Artifact` (Base Class)
- `HARArtifact(Artifact)`
- `TraceArtifact(Artifact)`
- `DOMArtifact(Artifact)`
- `JSArtifact(Artifact)`

### 2. The Global Timeline

#### [NEW] [portalmind/models/timeline.py](file:///f:/Playgrounds/bookingbot/portalmind/models/timeline.py)
Introduce Time as a first-class model to make correlation deterministic.
- `Timeline`: A unified ledger of events.
- `TimelineEvent`: A normalized event contributed by any artifact (Network Request, DOM Mutation, JS Invocation, Navigation).

### 3. Trace Ingestion & Normalization

#### [NEW] [portalmind/ingest/trace.py](file:///f:/Playgrounds/bookingbot/portalmind/ingest/trace.py)
- Parses the Playwright `.trace` archive.
- Normalizes its contents and pushes them into the global `Timeline` as `TimelineEvent`s.

### 4. Correlation & Analyzers

#### [NEW] [portalmind/analyzers/correlation.py](file:///f:/Playgrounds/bookingbot/portalmind/analyzers/correlation.py)
**Correlation Engine:**
- A generic engine that correlates events on the timeline using multiple robust signals: timestamp, frame, navigation, request ID, initiator, call stack, DOM node, and execution context.

#### [NEW] [portalmind/analyzers/dom.py](file:///f:/Playgrounds/bookingbot/portalmind/analyzers/dom.py)
**DOM Analyzer:**
- Ingests `TimelineEvent`s and injects `DOMElement` and `DOMEvent` nodes.

#### [NEW] [portalmind/analyzers/js.py](file:///f:/Playgrounds/bookingbot/portalmind/analyzers/js.py)
**JS Analyzer:**
- Consumes generic JavaScript artifacts (traces, source maps, bundles, console events) and correlates JS behavior with DOM and network activity.

#### [NEW] [portalmind/analyzers/navigation.py](file:///f:/Playgrounds/bookingbot/portalmind/analyzers/navigation.py)
**Navigation Analyzer:**
- Injects nodes related to routing: `Page -> Frame -> Navigation -> Redirect -> History -> State`. Essential for understanding SPA routing.

### 5. CLI Updates

#### [MODIFY] [portalmind/cli/__main__.py](file:///f:/Playgrounds/bookingbot/portalmind/cli/__main__.py)
- Refactor the pipeline to support the new flow:
  `Artifact -> Normalizer -> Timeline -> Correlation Engine / Analyzers -> Knowledge Graph -> Reasoners -> Planner`
- Add native support for `portalmind ingest trace <file.zip>`.

## Verification Plan

### Automated Tests
- Create a `synthetic.trace.zip` fixture to validate that multiple artifact types correctly push `TimelineEvent`s to the global `Timeline`.
- Assert that the `CorrelationEngine` correctly links a DOM event to a Network request using matching robust signals (e.g., matching execution contexts or frame IDs).
