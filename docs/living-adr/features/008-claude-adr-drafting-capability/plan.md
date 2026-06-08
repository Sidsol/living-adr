# Implementation Plan: claude-adr-drafting-capability

## Technical Context
Python 3.12, LangGraph, Anthropic SDK behind adapter, pytest, uv, Ruff. Inputs are Feature 004 contracts, Feature 007 `ArchitectureContextQuery`, and Feature 015 `WorkflowState`/`ADRDraftNode` seam. This plan writes no production code during planning; paths below are implementation targets.

## Planned File Layout
```text
src\living_adr\core\adr_draft.py
src\living_adr\core\llm.py
src\living_adr\workflow\drafting\policy.py
src\living_adr\workflow\drafting\context.py
src\living_adr\workflow\drafting\token_budget.py
src\living_adr\workflow\drafting\prompt.py
src\living_adr\workflow\drafting\claude_adapter.py
src\living_adr\workflow\drafting\parser.py
src\living_adr\workflow\nodes\adr_draft.py
src\living_adr\observability\drafting_events.py
tests\core\test_adr_draft_contract.py
tests\core\test_claude_client_fake.py
tests\workflow\drafting\test_policy.py
tests\workflow\drafting\test_context_packaging.py
tests\workflow\drafting\test_token_budget.py
tests\workflow\drafting\test_prompt_assembly.py
tests\workflow\drafting\test_claude_adapter.py
tests\workflow\drafting\test_draft_parser.py
tests\workflow\test_adr_draft_node.py
tests\workflow\test_adr_draft_node_no_mutation.py
tests\observability\test_drafting_events.py
```

## Tactical Steps

### S-001: Draft and Claude client contracts
- **TASK-001** Create `tests\core\test_adr_draft_contract.py`: RED tests for provisional flag, evidence/citation ids, model metadata, draft record candidate, and deterministic SHA-256 content hash.
- **TASK-002** Create `src\living_adr\core\adr_draft.py`: implement `ADRDraft`, citation refs, draft record projection, outcome enums, and hash helper.
- **TASK-003** Create `tests\core\test_claude_client_fake.py`: RED tests for protocol behavior, deterministic fake response, call recording, and no SDK/network dependency.
- **TASK-004** Create `src\living_adr\core\llm.py`: implement `ClaudeClient` protocol, request/response models, token metadata, error/result types, and `FakeClaudeClient`.

### S-002: LLM policy enforcement
- **TASK-005** Create `tests\workflow\drafting\test_policy.py`: RED tests for allow/deny, no-call-on-deny, and safe policy metadata.
- **TASK-006** Create `src\living_adr\workflow\drafting\policy.py`: implement `external_llm_allowed` evaluator and `llm_policy_denied` blocked result.

### S-003: Graph context packaging
- **TASK-007** Create `tests\workflow\drafting\test_context_packaging.py`: RED tests with fake `ArchitectureContextQuery` for scoped bounded calls, citation extraction, empty context, and no implementation leakage.
- **TASK-008** Create `src\living_adr\workflow\drafting\context.py`: implement context request builder, port calls, citation DTOs, empty marker, and deterministic ordering.

### S-004: Prompt assembly and token budget
- **TASK-009** Create `tests\workflow\drafting\test_token_budget.py`: RED tests for 8,000 default, priority order, required-section blocking, optional truncation, and omitted notes.
- **TASK-010** Create `src\living_adr\workflow\drafting\token_budget.py`: implement budget config, estimator abstraction, section priority, truncation/block result.
- **TASK-011** Create `tests\workflow\drafting\test_prompt_assembly.py`: RED tests for Feature 004 fields, evidence summaries, citations, ADR template, provisional labels, delimiters, and raw-diff exclusion.
- **TASK-012** Create `src\living_adr\workflow\drafting\prompt.py`: implement prompt sections and budget-integrated assembly.

### S-005: Claude adapter and output parser
- **TASK-013** Create `tests\workflow\drafting\test_claude_adapter.py`: RED tests using SDK mocks for model config, timeout/error mapping, token metadata, and no real network.
- **TASK-014** Create `src\living_adr\workflow\drafting\claude_adapter.py`: implement Anthropic-backed `ClaudeClient`, config, timeout handling, error mapping, and response metadata extraction.
- **TASK-015** Create `tests\workflow\drafting\test_draft_parser.py`: RED tests for valid Markdown ADR and failures on missing required sections/citations/provisional label.
- **TASK-016** Create `src\living_adr\workflow\drafting\parser.py`: implement section validation, citation extraction, provisional validation, and parser errors.

### S-006: Feature 015 draft node integration
- **TASK-017** Create `tests\workflow\test_adr_draft_node.py`: RED seam tests with fake Feature 015 state, Feature 004 change/evidence, fake query, and fake client.
- **TASK-018** Create `src\living_adr\workflow\nodes\adr_draft.py`: compose policy/context/budget/prompt/client/parser behind Feature 015 `ADRDraftNode` seam.
- **TASK-019** Create `tests\workflow\test_adr_draft_node_no_mutation.py`: RED tests proving no graph mutation, approval, audit, UI, or publish-back calls.
- **TASK-020** Modify `src\living_adr\workflow\nodes\adr_draft.py`: add no-ADR, missing evidence, policy denied, budget exceeded, provider error, and invalid output routing.

### S-007: Observability and blocked/error outcomes
- **TASK-021** Create `tests\observability\test_drafting_events.py`: RED tests for safe event fields and exclusion of raw prompts/diffs/drafts/responses.
- **TASK-022** Create `src\living_adr\observability\drafting_events.py`: implement started, policy_blocked, budget_blocked, provider_error, invalid_output, succeeded, completed event builders.
- **TASK-023** Modify `src\living_adr\workflow\nodes\adr_draft.py`: emit metadata-only events through inherited observability port.

## Machine-Readable Task Graph
```yaml
task_graph:
  - { id: TASK-001, slice: S-001, depends_on: [], files: [tests\core\test_adr_draft_contract.py] }
  - { id: TASK-002, slice: S-001, depends_on: [TASK-001], files: [src\living_adr\core\adr_draft.py] }
  - { id: TASK-003, slice: S-001, depends_on: [TASK-002], files: [tests\core\test_claude_client_fake.py] }
  - { id: TASK-004, slice: S-001, depends_on: [TASK-003], files: [src\living_adr\core\llm.py] }
  - { id: TASK-005, slice: S-002, depends_on: [TASK-004], files: [tests\workflow\drafting\test_policy.py] }
  - { id: TASK-006, slice: S-002, depends_on: [TASK-005], files: [src\living_adr\workflow\drafting\policy.py] }
  - { id: TASK-007, slice: S-003, depends_on: [TASK-004], files: [tests\workflow\drafting\test_context_packaging.py] }
  - { id: TASK-008, slice: S-003, depends_on: [TASK-007], files: [src\living_adr\workflow\drafting\context.py] }
  - { id: TASK-009, slice: S-004, depends_on: [TASK-006, TASK-008], files: [tests\workflow\drafting\test_token_budget.py] }
  - { id: TASK-010, slice: S-004, depends_on: [TASK-009], files: [src\living_adr\workflow\drafting\token_budget.py] }
  - { id: TASK-011, slice: S-004, depends_on: [TASK-010], files: [tests\workflow\drafting\test_prompt_assembly.py] }
  - { id: TASK-012, slice: S-004, depends_on: [TASK-011], files: [src\living_adr\workflow\drafting\prompt.py] }
  - { id: TASK-013, slice: S-005, depends_on: [TASK-012], files: [tests\workflow\drafting\test_claude_adapter.py] }
  - { id: TASK-014, slice: S-005, depends_on: [TASK-013], files: [src\living_adr\workflow\drafting\claude_adapter.py] }
  - { id: TASK-015, slice: S-005, depends_on: [TASK-014], files: [tests\workflow\drafting\test_draft_parser.py] }
  - { id: TASK-016, slice: S-005, depends_on: [TASK-015], files: [src\living_adr\workflow\drafting\parser.py] }
  - { id: TASK-017, slice: S-006, depends_on: [TASK-016], files: [tests\workflow\test_adr_draft_node.py] }
  - { id: TASK-018, slice: S-006, depends_on: [TASK-017], files: [src\living_adr\workflow\nodes\adr_draft.py] }
  - { id: TASK-019, slice: S-006, depends_on: [TASK-018], files: [tests\workflow\test_adr_draft_node_no_mutation.py] }
  - { id: TASK-020, slice: S-006, depends_on: [TASK-019], files: [src\living_adr\workflow\nodes\adr_draft.py] }
  - { id: TASK-021, slice: S-007, depends_on: [TASK-020], files: [tests\observability\test_drafting_events.py] }
  - { id: TASK-022, slice: S-007, depends_on: [TASK-021], files: [src\living_adr\observability\drafting_events.py] }
  - { id: TASK-023, slice: S-007, depends_on: [TASK-022], files: [src\living_adr\workflow\nodes\adr_draft.py] }
```

## Rollback Strategy
Because the feature is draft-only, rollback can restore Feature 015's stub node and remove drafting modules/tests. Do not ship any Claude integration without S-002 policy and S-004 budget gates.
