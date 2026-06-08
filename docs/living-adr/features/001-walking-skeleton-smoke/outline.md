# Implementation Outline: walking-skeleton-smoke

## Slice Strategy
The feature is decomposed into five thin vertical slices matching the feature-map estimate. Each slice adds one visible step to the end-to-end chain and includes tests at the behavior boundary. Slices are mostly sequential because the walking skeleton's value is the cumulative path from event replay to MCP-style answer.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| SL-001 | Replay merged-PR smoke event | US-1 | S | — | false | AFK | Deterministic fixture and normalization with no safety boundary beyond repository scoping. |
| SL-002 | Stub classify and draft ADR | US-2 | M | SL-001 | false | AFK | Pure deterministic stubs with golden-output tests and no external calls. |
| SL-003 | Stub HITL accept decision | US-3 | M | SL-002 | false | HITL | Touches review-gate semantics and must preserve meaningful approval language. |
| SL-004 | Approval-bound stub persistence | US-3 | M | SL-003 | false | HITL | Safety-critical mutation seam proving no bypass of approved decision. |
| SL-005 | MCP-style why query smoke | US-4 | M | SL-004 | false | HITL | Public agent/IDE context boundary must remain read-only and approved-context-only. |

## Slices

### SL-001: Replay merged-PR smoke event
**Scope:** Create the minimal repo/package scaffold, a seeded merged-PR-like fixture, and a workflow-service smoke entrypoint that normalizes it into a repository-scoped `SCMEvent`.

**User Stories:** US-1  
**Automation:** AFK  
**Automation Reason:** Deterministic fixture and normalization with no safety boundary beyond repository scoping.

**Deliverables:**
- `pyproject.toml` with minimal project/test commands.
- `src\living_adr\core\models.py` containing initial smoke domain models.
- `src\living_adr\workflow\smoke_fixture.py` containing the fixture and replay normalization.
- `src\living_adr\apps\workflow_service\main.py` exposing smoke replay.
- `tests\workflow\test_smoke_replay.py` covering event shape and duplicate id behavior.

**Checkpoint Criteria:**
- [ ] A smoke replay function returns exactly one `SCMEvent` with repository identity.
- [ ] Duplicate delivery id handling is deterministic in tests.
- [ ] No external network or LLM dependencies are required.

**Context Notes:**
- Key files: `core\models.py`, `workflow\smoke_fixture.py`, workflow app main, replay tests.
- Dependencies: none.
- Estimated complexity: Low.

### SL-002: Stub classify and draft ADR
**Scope:** Add deterministic classifier and draft renderer that turn the replayed event into one `StructuralChange`, one `ChangeEvidence`, and one explicitly provisional `ADRDraft`.

**User Stories:** US-2  
**Automation:** AFK  
**Automation Reason:** Pure deterministic stubs with golden-output tests and no external calls.

**Deliverables:**
- `src\living_adr\workflow\smoke_flow.py` with classify and draft steps.
- `src\living_adr\core\models.py` extended with `StructuralChange`, `ChangeEvidence`, and `ADRDraft`.
- `tests\workflow\test_stub_classify_and_draft.py` covering deterministic output and stub labels.

**Checkpoint Criteria:**
- [ ] The classifier emits exactly one dependency-like structural change for the fixture.
- [ ] The ADR draft includes context, decision, consequences, alternatives placeholder, and evidence citation.
- [ ] The draft text clearly says it is a deterministic smoke stub.

**Context Notes:**
- Key files: `smoke_flow.py`, `models.py`, classifier/draft tests.
- Dependencies: SL-001.
- Estimated complexity: Medium.

### SL-003: Stub HITL accept decision
**Scope:** Add a stub review accept action that hashes the rendered draft and returns an `ApprovedReviewDecision`-shaped object scoped to the same repository.

**User Stories:** US-3  
**Automation:** HITL  
**Automation Reason:** Touches review-gate semantics and must preserve meaningful approval language.

**Deliverables:**
- `src\living_adr\hitl\stub_review.py` with accept-only smoke review.
- `src\living_adr\core\models.py` extended with `ApprovalEvent` and `ApprovedReviewDecision` smoke fields.
- `tests\hitl\test_stub_review.py` covering draft hash, reviewer id, and repository mismatch rejection.

**Checkpoint Criteria:**
- [ ] Accept creates a decision with reviewer id, draft id, structural-change id, repository, and content hash.
- [ ] Mismatched repository/draft inputs fail before persistence.
- [ ] Tests and names identify accept as a smoke stub, not full HITL.

**Context Notes:**
- Key files: `hitl\stub_review.py`, `core\models.py`, HITL tests.
- Dependencies: SL-002.
- Estimated complexity: Medium.

### SL-004: Approval-bound stub persistence
**Scope:** Add a stub store/service that persists one approved `ADRRecord` only when supplied the approved decision and rejects unauthorized mutation attempts.

**User Stories:** US-3  
**Automation:** HITL  
**Automation Reason:** Safety-critical mutation seam proving no bypass of approved decision.

**Deliverables:**
- `src\living_adr\graph\stub_store.py` implementing approval-bound in-memory or local-file persistence.
- `src\living_adr\core\models.py` extended with `ADRRecord` and `WhyAnswer` basics.
- `tests\graph\test_approval_bound_stub_store.py` covering allowed and denied writes.
- `tests\workflow\test_smoke_e2e_to_persistence.py` covering event -> approved ADR record.

**Checkpoint Criteria:**
- [ ] Mutation without decision fails in a focused test.
- [ ] Mutation with matching decision stores exactly one approved `ADRRecord`.
- [ ] Persisted record links event, evidence, draft, and decision provenance.

**Context Notes:**
- Key files: `graph\stub_store.py`, `core\models.py`, persistence and E2E tests.
- Dependencies: SL-003.
- Estimated complexity: Medium.

### SL-005: MCP-style why query smoke
**Scope:** Add a read-only MCP-style query wrapper that calls approved-context query logic and returns one cited why answer from the persisted stub ADR record.

**User Stories:** US-4  
**Automation:** HITL  
**Automation Reason:** Public agent/IDE context boundary must remain read-only and approved-context-only.

**Deliverables:**
- `src\living_adr\apps\mcp_context_server\main.py` exposing `answer_why_smoke` or equivalent callable.
- `src\living_adr\graph\stub_store.py` read-side query function over approved ADR records.
- `tests\mcp\test_smoke_answer_why.py` covering approved-only answer and no-approved-context response.
- `tests\workflow\test_full_walking_skeleton_smoke.py` covering the complete path.

**Checkpoint Criteria:**
- [ ] Query returns answer text, ADR id, and citation for the seeded approved record.
- [ ] Query does not read pending drafts or unapproved evidence as authoritative context.
- [ ] Full smoke E2E test demonstrates replay -> draft -> accept -> persist -> answer.

**Context Notes:**
- Key files: MCP app main, stub store, full smoke test.
- Dependencies: SL-004.
- Estimated complexity: Medium.

## Slice Dependency Graph

```text
SL-001 -> SL-002 -> SL-003 -> SL-004 -> SL-005
```

## Slice Dependency Graph (Machine-Readable)

```yaml
slices:
  - id: SL-001
    name: Replay merged-PR smoke event
    depends_on: []
    parallelizable: false
    automation: AFK
    automation_reason: "Deterministic fixture and normalization with no safety boundary beyond repository scoping."
    checkpoint_criteria_count: 3
  - id: SL-002
    name: Stub classify and draft ADR
    depends_on: [SL-001]
    parallelizable: false
    automation: AFK
    automation_reason: "Pure deterministic stubs with golden-output tests and no external calls."
    checkpoint_criteria_count: 3
  - id: SL-003
    name: Stub HITL accept decision
    depends_on: [SL-002]
    parallelizable: false
    automation: HITL
    automation_reason: "Touches review-gate semantics and must preserve meaningful approval language."
    checkpoint_criteria_count: 3
  - id: SL-004
    name: Approval-bound stub persistence
    depends_on: [SL-003]
    parallelizable: false
    automation: HITL
    automation_reason: "Safety-critical mutation seam proving no bypass of approved decision."
    checkpoint_criteria_count: 3
  - id: SL-005
    name: MCP-style why query smoke
    depends_on: [SL-004]
    parallelizable: false
    automation: HITL
    automation_reason: "Public agent/IDE context boundary must remain read-only and approved-context-only."
    checkpoint_criteria_count: 3
```

## Context Management
- Maximum files open per slice: 5 for SL-001/SL-002, 6 for SL-003 through SL-005.
- Recommended reset points: after SL-002 and after SL-004.
- State that must carry across slices: canonical domain names, slice IDs, repository-scoped model fields, explicit stub/non-production labeling, and the rule that only approved `ADRRecord` data can answer MCP-style why queries.

## Verification Strategy
Run unit tests per slice plus a final smoke E2E test that proves event replay, deterministic classification, stub draft, stub approval, approval-bound persistence, and MCP-style why answer. Verification must include negative tests for duplicate replay, missing approval decision, and no-approved-context query.
