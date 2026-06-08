# Implementation Outline: langsmith-observability-quality

## Slice Strategy

The feature is decomposed around independently testable observability behaviors: adapter/config foundation, redaction enforcement, metrics instrumentation helpers, unauthorized-mutation/review tracking, and evaluation harness. The slices preserve feature 002's `Observability` port and avoid forcing downstream modules to import LangSmith.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| 1 | Adapter configuration and safe no-op fallback | US-1, US-5 | M | — | false | HITL | Establishes the external LangSmith boundary and must preserve feature 002's port exactly. |
| 2 | Default-deny metadata policy | US-1 | M | 1 | false | HITL | Security/privacy boundary for raw export and sensitive repositories. |
| 3 | Latency, token, and structured metric helpers | US-2, US-5 | M | 2 | true | AFK | Additive helper layer with deterministic unit tests after redaction is in place. |
| 4 | Draft outcome and mutation authorization tracking | US-3 | M | 2 | true | HITL | Touches SM-05 unauthorized-mutation monitoring and approval-bound semantics. |
| 5 | Retrieval and drafting evaluation harness | US-4 | L | 3, 4 | false | HITL | Owns SM-03/SM-04 regression signal design and fixture semantics. |

## Slices

### Slice 1: Adapter configuration and safe no-op fallback

**Scope:** Add LangSmith configuration, adapter factory, fake-client seam, and app wiring while preserving the feature 002 no-op fallback.

**User Stories:** US-1, US-5

**Automation:** HITL

**Automation Reason:** Establishes an external observability boundary and must be reviewed to ensure the existing `Observability` port is not redefined.

**Deliverables:**

- `src\living_adr\observability\config.py` for LangSmith enablement, project, endpoint, sampling, retention, raw-export flags.
- `src\living_adr\observability\langsmith_adapter.py` implementing feature 002's `Observability` port.
- `src\living_adr\observability\factory.py` selecting LangSmith or `NoOpObservability`.
- `src\living_adr\apps\workflow_service\observability.py` and `src\living_adr\apps\mcp_context_server\observability.py` bootstrap helpers.
- Tests with fake LangSmith client and no network I/O.

**Checkpoint Criteria:**

- [ ] With no LangSmith config, adapter factory returns no-op behavior and startup does not fail.
- [ ] With LangSmith config, adapter implements `record_event`, `increment_counter`, and `start_span` without changing the core port.
- [ ] No app/workflow/HITL/graph/MCP module imports LangSmith directly.
- [ ] Adapter errors are contained and do not raise during normal observability calls.

**Context Notes:**

- Key files: `src\living_adr\core\observability.py`, `src\living_adr\observability\config.py`, `src\living_adr\observability\langsmith_adapter.py`, startup helpers.
- Dependencies: feature 002 core port and config models.
- Estimated complexity: Medium.

### Slice 2: Default-deny metadata policy

**Scope:** Enforce metadata-only traces with default-deny raw export, forbidden-key redaction, sensitive repository override, and structured redaction logs.

**User Stories:** US-1

**Automation:** HITL

**Automation Reason:** Implements the FM-21 security/privacy boundary and default-deny raw egress controls.

**Deliverables:**

- `src\living_adr\observability\redaction.py` with allowed metadata scalars, forbidden raw keys, nested redaction, and repository policy checks.
- `src\living_adr\observability\logging.py` for safe structured events and redaction diagnostics.
- Tests for raw diffs, prompts, drafts, reviewer comments, retrieved context, code snippets, secrets, personal data, debug raw export, and sensitive repo override.

**Checkpoint Criteria:**

- [ ] Forbidden raw keys are rejected/redacted before LangSmith export.
- [ ] Opt-in raw export remains denied for sensitive repositories.
- [ ] Structured redaction events contain only safe identifiers and reason codes.
- [ ] Unit tests prove metadata-only traces for normal and nested metadata inputs.

**Context Notes:**

- Key files: `redaction.py`, `logging.py`, `langsmith_adapter.py`, `tests\observability\test_redaction.py`.
- Dependencies: Slice 1 adapter seam.
- Estimated complexity: Medium.

### Slice 3: Latency, token, and structured metric helpers

**Scope:** Add consistent metric names and helper functions for stage latency, PR-to-draft latency, token counts, retries, and error types.

**User Stories:** US-2, US-5

**Automation:** AFK

**Automation Reason:** Purely additive helper layer with deterministic tests once Slice 2 enforces redaction.

**Deliverables:**

- `src\living_adr\observability\metrics.py` defining safe metadata keys and helper functions.
- Instrumentation call sites or seam wrappers for workflow stage spans, Claude token usage, retrieval/MCP latency, and evaluation latency.
- Tests for emitted metadata shape and redaction compatibility.

**Checkpoint Criteria:**

- [ ] Stage spans emit elapsed milliseconds with repository key/run id where applicable.
- [ ] Token usage emits numeric prompt/completion/total counts only.
- [ ] Error/retry events emit type and count but no payload stack traces.
- [ ] Metrics helper tests do not require LangSmith credentials or network access.

**Context Notes:**

- Key files: `metrics.py`, likely future call sites in `workflow`, `hitl`, `graph`, `apps\mcp_context_server`.
- Dependencies: Slice 2 safe metadata policy.
- Estimated complexity: Medium.

### Slice 4: Draft outcome and mutation authorization tracking

**Scope:** Add observability helpers and call-site plans for HITL draft outcomes and approval-bound mutation checks.

**User Stories:** US-3

**Automation:** HITL

**Automation Reason:** Aligns with SM-05 and approval-bound mutation semantics, requiring careful review of authorization failure reason codes.

**Deliverables:**

- `src\living_adr\observability\decisions.py` helper functions for draft outcomes and mutation authorization events.
- Tests for approved, approved-after-edit, rejected, deferred, unauthorized failure reasons, and successful mutation events.
- Integration notes/call sites for HITL review and `ApprovalBoundMutationService` once those features exist.

**Checkpoint Criteria:**

- [ ] Draft outcome counters include repository key, draft id, change class, outcome, and reviewer role only.
- [ ] Unauthorized-mutation events are emitted for missing/expired/reused/mismatched/rejected decisions.
- [ ] Successful mutation events include safe decision id, mutation type, latency, and status.
- [ ] No ADR body, reviewer comment, or raw draft content appears in emitted metadata.

**Context Notes:**

- Key files: `decisions.py`, `metrics.py`, `redaction.py`, future HITL/graph call sites.
- Dependencies: Slice 2 safe metadata policy.
- Estimated complexity: Medium.

### Slice 5: Retrieval and drafting evaluation harness

**Scope:** Add versioned fixture schemas, retrieval and drafting evaluation runners, machine-readable output, and observability of evaluation runs.

**User Stories:** US-4

**Automation:** HITL

**Automation Reason:** Owns SM-03/SM-04 evaluation semantics and must avoid overfitting or false claims of quality.

**Deliverables:**

- `src\living_adr\observability\evals\fixtures.py` for fixture schemas.
- `src\living_adr\observability\evals\retrieval.py` for SM-03/SM-04 query evaluation.
- `src\living_adr\observability\evals\drafting.py` for drafting regression checks.
- `src\living_adr\observability\evals\runner.py` or CLI command wrapper.
- `tests\fixtures\evals\heldout_queries.example.yaml` and drafting examples.
- Tests for pass/fail/regression output.

**Checkpoint Criteria:**

- [ ] Retrieval evaluation reports per-query expected citation hits/misses, relevance status, and coverage status.
- [ ] Drafting evaluation reports evidence citation, alternatives, consequences, and provisional-rationale checks.
- [ ] Evaluation output is machine-readable and non-zero/failing when configured regression thresholds are violated.
- [ ] Evaluation fixtures include version metadata and at least one edge/rejected example.

**Context Notes:**

- Key files: `observability\evals\*`, `tests\evals\*`, `tests\fixtures\evals\*`.
- Dependencies: Slices 3 and 4 metric helpers.
- Estimated complexity: High.

## Slice Dependency Graph

```text
Slice 1 ──→ Slice 2 ──→ Slice 3 ──┐
                    └──→ Slice 4 ──┤
                                    └──→ Slice 5
```

## Slice Dependency Graph (Machine-Readable)

```yaml
slices:
  - id: 1
    name: Adapter configuration and safe no-op fallback
    depends_on: []
    parallelizable: false
    automation: HITL
    automation_reason: "Establishes the external LangSmith boundary and must preserve feature 002's port exactly."
    checkpoint_criteria_count: 4
  - id: 2
    name: Default-deny metadata policy
    depends_on: [1]
    parallelizable: false
    automation: HITL
    automation_reason: "Security/privacy boundary for raw export and sensitive repositories."
    checkpoint_criteria_count: 4
  - id: 3
    name: Latency token and structured metric helpers
    depends_on: [2]
    parallelizable: true
    automation: AFK
    automation_reason: "Additive helper layer with deterministic unit tests after redaction is in place."
    checkpoint_criteria_count: 4
  - id: 4
    name: Draft outcome and mutation authorization tracking
    depends_on: [2]
    parallelizable: true
    automation: HITL
    automation_reason: "Touches SM-05 unauthorized-mutation monitoring and approval-bound semantics."
    checkpoint_criteria_count: 4
  - id: 5
    name: Retrieval and drafting evaluation harness
    depends_on: [3, 4]
    parallelizable: false
    automation: HITL
    automation_reason: "Owns SM-03/SM-04 regression signal design and fixture semantics."
    checkpoint_criteria_count: 4
```

## Context Management

- Maximum files open per slice: 6 implementation files plus focused tests.
- Recommended context reset points: after Slice 2 and before Slice 5.
- State that must carry across slices: feature 002 port method names; default-deny raw export policy; repository-scoped metadata keys; SM-01 through SM-05 metric mapping.

## Verification Strategy

- Run existing project tests after each slice.
- Add fake-client unit tests for LangSmith adapter and redaction; no live LangSmith tests in CI.
- Run evaluation harness against sample fixtures and verify machine-readable output.
- Search for forbidden direct `langsmith` imports outside `src\living_adr\observability`.
- Verify no emitted metadata includes forbidden raw field names or payload values.
