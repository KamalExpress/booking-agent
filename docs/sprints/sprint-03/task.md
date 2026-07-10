# Sprint 03: Multi-Artifact Correlation Engine Tasks

- `[x]` Formal Artifact Models
  - `[x]` Create `portalmind/models/artifact.py` with `Artifact`, `HARArtifact`, `TraceArtifact`, etc.
- `[x]` Global Timeline
  - `[x]` Create `portalmind/models/timeline.py` with `Timeline` and `TimelineEvent`
- `[x]` Trace Ingestion
  - `[x]` Create `portalmind/ingest/trace.py`
  - `[x]` Update `portalmind/normalize/` to produce `TimelineEvent`s
- `[x]` Correlation & Analyzers
  - `[x]` Create `portalmind/analyzers/correlation.py` (`CorrelationEngine`)
  - `[x]` Create `portalmind/analyzers/dom.py` (`DOMAnalyzer`)
  - `[x]` Create `portalmind/analyzers/js.py` (`JSAnalyzer`)
  - `[x]` Create `portalmind/analyzers/navigation.py` (`NavigationAnalyzer`)
- `[x]` Pipeline Updates
  - `[x]` Refactor `portalmind/cli/__main__.py` to use `Timeline` and `CorrelationEngine`
- `[x]` Testing
  - `[x]` Write `synthetic.trace.json` or similar for tests
  - `[x]` Update `test_pipeline.py` to assert correct correlations
