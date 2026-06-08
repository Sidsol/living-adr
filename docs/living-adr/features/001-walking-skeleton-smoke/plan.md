# Implementation Plan: walking-skeleton-smoke

## Technical Context
- Language/Framework: Python 3.12, minimal FastAPI-compatible app entry modules.
- Key Dependencies: project stack eventually includes FastAPI, LangGraph, MCP SDK, SQLite/LlamaIndex; this feature should keep smoke code deterministic and avoid external service calls.
- Test Framework: pytest.
- Build System: uv / pyproject.toml.
- Architecture anchors: `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`, `..\..\architecture.md#deployment`, `..\..\architecture.md#anti-patterns`.

## Project Structure

```text
C:\repos\living-adr\
  pyproject.toml                                  ← CREATE: minimal package/test config if absent
  src\living_adr\
    __init__.py                                  ← CREATE
    core\
      __init__.py                                ← CREATE
      models.py                                  ← CREATE: smoke domain records
    workflow\
      __init__.py                                ← CREATE
      smoke_fixture.py                           ← CREATE: seeded merged-PR-like event
      smoke_flow.py                              ← CREATE: deterministic classify/draft/orchestrate
    hitl\
      __init__.py                                ← CREATE
      stub_review.py                             ← CREATE: accept-only smoke review decision
    graph\
      __init__.py                                ← CREATE
      stub_store.py                              ← CREATE: approval-bound stub store/query projection
    apps\
      __init__.py                                ← CREATE
      workflow_service\
        __init__.py                              ← CREATE
        main.py                                  ← CREATE: smoke workflow app/CLI function
      mcp_context_server\
        __init__.py                              ← CREATE
        main.py                                  ← CREATE: MCP-style answer_why wrapper
tests\
  workflow\
    test_smoke_replay.py                         ← CREATE
    test_stub_classify_and_draft.py              ← CREATE
    test_smoke_e2e_to_persistence.py             ← CREATE
    test_full_walking_skeleton_smoke.py          ← CREATE
  hitl\
    test_stub_review.py                          ← CREATE
  graph\
    test_approval_bound_stub_store.py            ← CREATE
  mcp\
    test_smoke_answer_why.py                     ← CREATE
```

## Implementation Phases

### Phase SL-001: Replay merged-PR smoke event

#### TASK-001: Create replay tests first
- **File:** `tests\workflow\test_smoke_replay.py`
- **Action:** Create
- **Changes:** RED tests for fixture normalization into one repository-scoped `SCMEvent`, stable delivery id, and duplicate replay behavior.

#### TASK-002: Create minimal project scaffold and core event models
- **Files:** `pyproject.toml`, `src\living_adr\__init__.py`, `src\living_adr\core\__init__.py`, `src\living_adr\core\models.py`
- **Action:** Create
- **Changes:** Define minimal package config and dataclasses/Pydantic-style records for `RepositoryIdentity` and `SCMEvent` used by smoke tests.

#### TASK-003: Implement replay fixture and workflow-service smoke entry
- **Files:** `src\living_adr\workflow\__init__.py`, `src\living_adr\workflow\smoke_fixture.py`, `src\living_adr\apps\__init__.py`, `src\living_adr\apps\workflow_service\__init__.py`, `src\living_adr\apps\workflow_service\main.py`
- **Action:** Create
- **Changes:** Add seeded merged-PR-like fixture, normalization function, duplicate delivery tracking for smoke scope, and callable app entrypoint.

### Phase SL-002: Stub classify and draft ADR

#### TASK-004: Create classifier/draft tests first
- **File:** `tests\workflow\test_stub_classify_and_draft.py`
- **Action:** Create
- **Changes:** RED tests for one deterministic structural change, evidence citation, ADR draft shape, and explicit smoke-stub labeling.

#### TASK-005: Extend core models for structural change and draft
- **File:** `src\living_adr\core\models.py`
- **Action:** Modify
- **Changes:** Add `StructuralChange`, `ChangeEvidence`, and `ADRDraft` records with repository scope, ids, evidence citation fields, and rendered markdown/text.

#### TASK-006: Implement deterministic smoke classify/draft flow
- **File:** `src\living_adr\workflow\smoke_flow.py`
- **Action:** Create
- **Changes:** Add deterministic classifier and ADR draft renderer. Do not call Claude or external services.

### Phase SL-003: Stub HITL accept decision

#### TASK-007: Create HITL review tests first
- **File:** `tests\hitl\test_stub_review.py`
- **Action:** Create
- **Changes:** RED tests for reviewer id, draft content hash, structural-change id linkage, repository scope, and mismatch rejection.

#### TASK-008: Extend core models for review decision
- **File:** `src\living_adr\core\models.py`
- **Action:** Modify
- **Changes:** Add `ApprovalEvent` and `ApprovedReviewDecision` smoke fields matching architecture shape at minimal depth.

#### TASK-009: Implement accept-only stub review
- **Files:** `src\living_adr\hitl\__init__.py`, `src\living_adr\hitl\stub_review.py`
- **Action:** Create
- **Changes:** Add accept action that hashes reviewed draft content and returns an approved decision object. Reject mismatched repository/draft inputs.

### Phase SL-004: Approval-bound stub persistence

#### TASK-010: Create persistence guard tests first
- **File:** `tests\graph\test_approval_bound_stub_store.py`
- **Action:** Create
- **Changes:** RED tests that mutation without decision fails, mutation with matching decision succeeds once, and record provenance is retained.

#### TASK-011: Extend core models for ADR record and answer basics
- **File:** `src\living_adr\core\models.py`
- **Action:** Modify
- **Changes:** Add `ADRRecord`, citation/provenance fields, and minimal `WhyAnswer` model for later query use.

#### TASK-012: Implement approval-bound stub store and persistence E2E
- **Files:** `src\living_adr\graph\__init__.py`, `src\living_adr\graph\stub_store.py`, `tests\workflow\test_smoke_e2e_to_persistence.py`
- **Action:** Create
- **Changes:** Add write method requiring matching approved decision, approved-record storage, approved-only list/fetch helpers, and E2E test through persistence.

### Phase SL-005: MCP-style why query smoke

#### TASK-013: Create MCP-style query tests first
- **File:** `tests\mcp\test_smoke_answer_why.py`
- **Action:** Create
- **Changes:** RED tests for approved-context answer, citation fields, read-only behavior, and no-approved-context response.

#### TASK-014: Implement MCP-style read wrapper
- **Files:** `src\living_adr\apps\mcp_context_server\__init__.py`, `src\living_adr\apps\mcp_context_server\main.py`, `src\living_adr\graph\stub_store.py`
- **Action:** Create/Modify
- **Changes:** Add `answer_why_smoke` wrapper over approved-only query logic. Keep it read-only and free of SCM/write dependencies.

#### TASK-015: Add full walking-skeleton smoke test
- **File:** `tests\workflow\test_full_walking_skeleton_smoke.py`
- **Action:** Create
- **Changes:** Test full replay -> classify -> draft -> accept -> persist -> answer path, asserting stub labels and approved-only citations.

## Complexity Tracking

| Phase | Files Changed | New Files | Estimated Effort | Risk |
|---|---:|---:|---|---|
| SL-001 | 0 | 8 | 1-2 hours | Low |
| SL-002 | 1 | 2 | 2-3 hours | Medium |
| SL-003 | 1 | 3 | 2-3 hours | Medium |
| SL-004 | 1 | 4 | 2-3 hours | High |
| SL-005 | 1 | 3 | 2-3 hours | High |

## Dependencies & Prerequisites
- `C:\repos\living-adr` may need to be created/scaffolded by the implementer because it is absent during planning.
- Python 3.12 and uv should be available per architecture.
- No GitHub credentials, Anthropic key, LangSmith key, or real MCP host are required for this feature.
- Use local deterministic tests only.

## Rollback Strategy
- Because the feature is additive and greenfield, rollback by deleting the created smoke modules/tests and reverting `pyproject.toml` if it was introduced only for this feature.
- Keep stub names isolated (`smoke_`, `stub_`) so later replacement does not require deleting production-looking APIs.
- If a phase fails, do not keep partial mutation-seam code without its corresponding negative tests.

## Machine-Readable Task Graph

```yaml
task_graph:
  - id: TASK-001
    slice: SL-001
    story: US-1
    depends_on: []
    parallelizable_with: []
    files: [tests\workflow\test_smoke_replay.py]
  - id: TASK-002
    slice: SL-001
    story: US-1
    depends_on: [TASK-001]
    parallelizable_with: []
    files: [pyproject.toml, src\living_adr\__init__.py, src\living_adr\core\__init__.py, src\living_adr\core\models.py]
  - id: TASK-003
    slice: SL-001
    story: US-1
    depends_on: [TASK-002]
    parallelizable_with: []
    files: [src\living_adr\workflow\__init__.py, src\living_adr\workflow\smoke_fixture.py, src\living_adr\apps\__init__.py, src\living_adr\apps\workflow_service\__init__.py, src\living_adr\apps\workflow_service\main.py]
  - id: TASK-004
    slice: SL-002
    story: US-2
    depends_on: [TASK-003]
    parallelizable_with: []
    files: [tests\workflow\test_stub_classify_and_draft.py]
  - id: TASK-005
    slice: SL-002
    story: US-2
    depends_on: [TASK-004]
    parallelizable_with: []
    files: [src\living_adr\core\models.py]
  - id: TASK-006
    slice: SL-002
    story: US-2
    depends_on: [TASK-005]
    parallelizable_with: []
    files: [src\living_adr\workflow\smoke_flow.py]
  - id: TASK-007
    slice: SL-003
    story: US-3
    depends_on: [TASK-006]
    parallelizable_with: []
    files: [tests\hitl\test_stub_review.py]
  - id: TASK-008
    slice: SL-003
    story: US-3
    depends_on: [TASK-007]
    parallelizable_with: []
    files: [src\living_adr\core\models.py]
  - id: TASK-009
    slice: SL-003
    story: US-3
    depends_on: [TASK-008]
    parallelizable_with: []
    files: [src\living_adr\hitl\__init__.py, src\living_adr\hitl\stub_review.py]
  - id: TASK-010
    slice: SL-004
    story: US-3
    depends_on: [TASK-009]
    parallelizable_with: []
    files: [tests\graph\test_approval_bound_stub_store.py]
  - id: TASK-011
    slice: SL-004
    story: US-3
    depends_on: [TASK-010]
    parallelizable_with: []
    files: [src\living_adr\core\models.py]
  - id: TASK-012
    slice: SL-004
    story: US-3
    depends_on: [TASK-011]
    parallelizable_with: []
    files: [src\living_adr\graph\__init__.py, src\living_adr\graph\stub_store.py, tests\workflow\test_smoke_e2e_to_persistence.py]
  - id: TASK-013
    slice: SL-005
    story: US-4
    depends_on: [TASK-012]
    parallelizable_with: []
    files: [tests\mcp\test_smoke_answer_why.py]
  - id: TASK-014
    slice: SL-005
    story: US-4
    depends_on: [TASK-013]
    parallelizable_with: []
    files: [src\living_adr\apps\mcp_context_server\__init__.py, src\living_adr\apps\mcp_context_server\main.py, src\living_adr\graph\stub_store.py]
  - id: TASK-015
    slice: SL-005
    story: US-4
    depends_on: [TASK-014]
    parallelizable_with: []
    files: [tests\workflow\test_full_walking_skeleton_smoke.py]
```
