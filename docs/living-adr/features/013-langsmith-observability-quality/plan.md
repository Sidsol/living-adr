# Implementation Plan: langsmith-observability-quality

## Technical Context

- Language/Framework: Python 3.12, FastAPI app bootstrap, LangGraph/LlamaIndex callers through ports.
- Key Dependencies: `langsmith==0.8.5`, existing feature 002 `Observability` port, repository config models, pytest.
- Test Framework: pytest.
- Build System: uv workspace with Ruff.
- Architecture Anchors: `..\..\architecture.md#tech-stack`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#data-model`, `..\..\architecture.md#anti-patterns`.

## Project Structure

```text
src\living_adr\
├── core\
│   └── observability.py                  ← EXISTING FROM 002: do not redefine port
├── observability\
│   ├── __init__.py                       ← NEW: package exports
│   ├── config.py                         ← NEW: LangSmith config/sampling/retention/raw export policy
│   ├── factory.py                        ← NEW: select LangSmith or NoOpObservability
│   ├── langsmith_adapter.py              ← NEW: port implementation with fake-client seam
│   ├── redaction.py                      ← NEW: metadata-only/default-deny policy
│   ├── logging.py                        ← NEW: safe structured logging
│   ├── metrics.py                        ← NEW: latency/token/retry metric helpers
│   ├── decisions.py                      ← NEW: draft outcome and mutation authorization helpers
│   └── evals\
│       ├── __init__.py                   ← NEW
│       ├── fixtures.py                   ← NEW: fixture schemas
│       ├── retrieval.py                  ← NEW: SM-03/SM-04 evaluator
│       ├── drafting.py                   ← NEW: drafting evaluator
│       └── runner.py                     ← NEW: CLI/local runner orchestration
├── apps\workflow_service\
│   └── observability.py                  ← NEW/MODIFY: bootstrap helper
└── apps\mcp_context_server\
    └── observability.py                  ← NEW/MODIFY: bootstrap helper

tests\
├── observability\
│   ├── test_langsmith_adapter.py         ← NEW
│   ├── test_redaction.py                 ← NEW
│   ├── test_metrics.py                   ← NEW
│   └── test_decisions.py                 ← NEW
├── evals\
│   ├── test_retrieval_eval.py            ← NEW
│   └── test_drafting_eval.py             ← NEW
└── fixtures\evals\
    ├── heldout_queries.example.yaml      ← NEW
    └── drafting_cases.example.yaml       ← NEW
```

## Implementation Phases

### Phase 1: Adapter configuration and safe no-op fallback

#### Step 1.1: Define LangSmith observability settings

- **File:** `src\living_adr\observability\config.py`
- **Action:** Create
- **Changes:** Add typed settings for enabled flag, project name, endpoint, sampling rate, retention days, raw export debug flag, and sensitive repository override handling. Default to disabled/no-op and raw export false.

#### Step 1.2: Implement LangSmith adapter behind the existing port

- **File:** `src\living_adr\observability\langsmith_adapter.py`
- **Action:** Create
- **Changes:** Implement `record_event`, `increment_counter`, and `start_span` matching `src\living_adr\core\observability.py`; accept an injectable fake/real client; catch adapter errors; emit safe local logs.

#### Step 1.3: Add adapter factory and app bootstrap helpers

- **Files:** `src\living_adr\observability\factory.py`, `src\living_adr\apps\workflow_service\observability.py`, `src\living_adr\apps\mcp_context_server\observability.py`, `src\living_adr\observability\__init__.py`
- **Action:** Create/Modify
- **Changes:** Select `LangSmithObservability` only when configured; otherwise use `NoOpObservability`. Keep apps dependent on core port type only.

#### Step 1.4: Test adapter/no-op selection

- **File:** `tests\observability\test_langsmith_adapter.py`
- **Action:** Create
- **Changes:** Add fake-client tests for no-op fallback, port method compatibility, span context manager behavior, and swallowed adapter failures.

### Phase 2: Default-deny metadata policy

#### Step 2.1: Implement metadata redaction and raw export policy

- **File:** `src\living_adr\observability\redaction.py`
- **Action:** Create
- **Changes:** Define safe scalar metadata, forbidden raw keys, nested redaction behavior, sensitive repository override, opt-in debug raw export checks, and reason codes.

#### Step 2.2: Add safe structured logging

- **File:** `src\living_adr\observability\logging.py`
- **Action:** Create
- **Changes:** Emit JSON-compatible safe log records for events, counters, spans, and redaction diagnostics.

#### Step 2.3: Wire redaction into LangSmith adapter

- **File:** `src\living_adr\observability\langsmith_adapter.py`
- **Action:** Modify
- **Changes:** Redact metadata before client calls and logs; include redaction diagnostics without raw values.

#### Step 2.4: Test default-deny policy

- **File:** `tests\observability\test_redaction.py`
- **Action:** Create
- **Changes:** Cover raw diffs, prompts, drafts, reviewer comments, retrieved context, code snippets, secrets, personal data, nested objects, debug raw export, and sensitive repo override.

### Phase 3: Latency, token, and structured metric helpers

#### Step 3.1: Define metric names and helper functions

- **File:** `src\living_adr\observability\metrics.py`
- **Action:** Create
- **Changes:** Add helpers for stage span metadata, PR-to-draft latency, model token usage, retrieval/MCP latency, retry counts, and error types.

#### Step 3.2: Add metric helper tests

- **File:** `tests\observability\test_metrics.py`
- **Action:** Create
- **Changes:** Assert emitted metadata shape, numeric-only token counts, latency units, repository scope, and redaction compatibility.

#### Step 3.3: Document/codify planned instrumentation call sites

- **File:** `src\living_adr\observability\metrics.py`
- **Action:** Modify
- **Changes:** Add typed helper names that downstream workflow, Claude, retrieval, MCP, and eval code can call without knowing LangSmith.

### Phase 4: Draft outcome and mutation authorization tracking

#### Step 4.1: Add decision/mutation observability helpers

- **File:** `src\living_adr\observability\decisions.py`
- **Action:** Create
- **Changes:** Add helper functions for draft approved, approved-after-edit, rejected, deferred, unauthorized mutation failure reason, and approved mutation success events.

#### Step 4.2: Test decision and mutation metadata safety

- **File:** `tests\observability\test_decisions.py`
- **Action:** Create
- **Changes:** Assert safe identifiers only, expected SM-01/SM-05 event names, reason-code coverage, and no ADR body/reviewer-comment metadata.

#### Step 4.3: Add integration TODO/seam comments only where necessary

- **Files:** future HITL/graph call-site modules when present
- **Action:** Modify as implementation-time availability permits
- **Changes:** Wire helper calls into real review/mutation paths if those features already exist; otherwise expose helpers and tests for downstream use without creating fake production logic.

### Phase 5: Retrieval and drafting evaluation harness

#### Step 5.1: Define fixture schemas

- **File:** `src\living_adr\observability\evals\fixtures.py`
- **Action:** Create
- **Changes:** Define versioned held-out query and drafting fixture models with repository key, case id, expected ADR/rationale references, expected checks, labels, and edge/rejected case metadata.

#### Step 5.2: Add retrieval evaluator

- **File:** `src\living_adr\observability\evals\retrieval.py`
- **Action:** Create
- **Changes:** Run cases against `ArchitectureContextQuery.answer_why(...)`, compare cited ADRs/references, compute relevance and coverage pass/fail/regression signals, and emit observability events.

#### Step 5.3: Add drafting evaluator

- **File:** `src\living_adr\observability\evals\drafting.py`
- **Action:** Create
- **Changes:** Validate draft outputs for evidence citations, alternatives, consequences, provisional-rationale labeling, and fixture-specific expected signals.

#### Step 5.4: Add runner and sample fixtures

- **Files:** `src\living_adr\observability\evals\runner.py`, `tests\fixtures\evals\heldout_queries.example.yaml`, `tests\fixtures\evals\drafting_cases.example.yaml`
- **Action:** Create
- **Changes:** Provide local/CI entry point and example fixtures for tests and future PoC baselines.

#### Step 5.5: Test evaluation output and regression behavior

- **Files:** `tests\evals\test_retrieval_eval.py`, `tests\evals\test_drafting_eval.py`
- **Action:** Create
- **Changes:** Use fake query/draft adapters; assert machine-readable output, pass/fail aggregation, non-zero/failing regression signal where configured, and safe observability metadata.

## Complexity Tracking

| Phase | Files Changed | New Files | Estimated Effort | Risk |
|---|---:|---:|---|---|
| Phase 1 | 1 | 5 | Medium | Medium |
| Phase 2 | 1 | 3 | Medium | High |
| Phase 3 | 1 | 1 | Medium | Low |
| Phase 4 | 0-2 | 2 | Medium | Medium |
| Phase 5 | 0 | 7 | Large | Medium |

## Dependencies & Prerequisites

- Feature 002 must define `src\living_adr\core\observability.py` and config/repository identity models.
- `langsmith==0.8.5` must be available from project dependencies per `..\..\architecture.md#tech-stack`.
- Tests must use fake LangSmith clients; live credentials are not required for CI.
- If feature 008/009/010/012/015 call sites are not implemented yet, this feature should expose helpers and tests without inventing their production logic.

## Rollback Strategy

- Phase 1: Set LangSmith enabled flag false or use factory fallback to `NoOpObservability`.
- Phase 2: If redaction policy is unsafe or broken, disable LangSmith adapter and preserve no-op/log-only behavior.
- Phase 3: Remove helper calls while keeping no-op-safe port behavior.
- Phase 4: Disable decision/mutation helper calls; audit logic remains authoritative outside observability.
- Phase 5: Remove eval CLI from CI gating while preserving fixtures and local runner for iteration.

## Machine-Readable Task Graph

```yaml
task_graph:
  - id: TASK-001
    slice: 1
    story: US-1
    depends_on: []
    parallelizable_with: []
    files: [src\living_adr\observability\config.py]
  - id: TASK-002
    slice: 1
    story: US-1
    depends_on: [TASK-001]
    parallelizable_with: []
    files: [src\living_adr\observability\langsmith_adapter.py]
  - id: TASK-003
    slice: 1
    story: US-5
    depends_on: [TASK-001, TASK-002]
    parallelizable_with: []
    files: [src\living_adr\observability\factory.py, src\living_adr\apps\workflow_service\observability.py, src\living_adr\apps\mcp_context_server\observability.py, src\living_adr\observability\__init__.py]
  - id: TASK-004
    slice: 1
    story: US-1
    depends_on: [TASK-002, TASK-003]
    parallelizable_with: []
    files: [tests\observability\test_langsmith_adapter.py]
  - id: TASK-005
    slice: 2
    story: US-1
    depends_on: [TASK-004]
    parallelizable_with: []
    files: [src\living_adr\observability\redaction.py]
  - id: TASK-006
    slice: 2
    story: US-1
    depends_on: [TASK-005]
    parallelizable_with: []
    files: [src\living_adr\observability\logging.py]
  - id: TASK-007
    slice: 2
    story: US-1
    depends_on: [TASK-005, TASK-006]
    parallelizable_with: []
    files: [src\living_adr\observability\langsmith_adapter.py]
  - id: TASK-008
    slice: 2
    story: US-1
    depends_on: [TASK-007]
    parallelizable_with: []
    files: [tests\observability\test_redaction.py]
  - id: TASK-009
    slice: 3
    story: US-2
    depends_on: [TASK-008]
    parallelizable_with: [TASK-011]
    files: [src\living_adr\observability\metrics.py]
  - id: TASK-010
    slice: 3
    story: US-2
    depends_on: [TASK-009]
    parallelizable_with: [TASK-011, TASK-012]
    files: [tests\observability\test_metrics.py]
  - id: TASK-011
    slice: 4
    story: US-3
    depends_on: [TASK-008]
    parallelizable_with: [TASK-009, TASK-010]
    files: [src\living_adr\observability\decisions.py]
  - id: TASK-012
    slice: 4
    story: US-3
    depends_on: [TASK-011]
    parallelizable_with: [TASK-010]
    files: [tests\observability\test_decisions.py]
  - id: TASK-013
    slice: 5
    story: US-4
    depends_on: [TASK-010, TASK-012]
    parallelizable_with: []
    files: [src\living_adr\observability\evals\fixtures.py, src\living_adr\observability\evals\__init__.py]
  - id: TASK-014
    slice: 5
    story: US-4
    depends_on: [TASK-013]
    parallelizable_with: []
    files: [src\living_adr\observability\evals\retrieval.py]
  - id: TASK-015
    slice: 5
    story: US-4
    depends_on: [TASK-013]
    parallelizable_with: []
    files: [src\living_adr\observability\evals\drafting.py]
  - id: TASK-016
    slice: 5
    story: US-4
    depends_on: [TASK-014, TASK-015]
    parallelizable_with: []
    files: [src\living_adr\observability\evals\runner.py, tests\fixtures\evals\heldout_queries.example.yaml, tests\fixtures\evals\drafting_cases.example.yaml]
  - id: TASK-017
    slice: 5
    story: US-4
    depends_on: [TASK-016]
    parallelizable_with: []
    files: [tests\evals\test_retrieval_eval.py, tests\evals\test_drafting_eval.py]
```
