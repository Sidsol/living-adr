# Implementation Outline: claude-adr-drafting-capability

## Slice Strategy
Seven vertical slices match the feature-map estimate. Each slice is independently testable, uses fake dependencies, and preserves the no-authoritative-mutation boundary.

## Slice Table
| Slice | Name | Stories | Depends On | Automation | Reason |
|---|---|---|---|---|---|
| S-001 | Draft and Claude client contracts | US-1, US-5 | — | HITL | Establishes DTOs and fake-client seam used by all later work. |
| S-002 | LLM policy enforcement | US-3 | S-001 | HITL | Controls external data egress. |
| S-003 | Graph context packaging | US-2 | S-001 | HITL | Enforces Feature 007 query-port-only context. |
| S-004 | Prompt assembly and token budget | US-1, US-4 | S-002, S-003 | HITL | Determines external prompt content and budget behavior. |
| S-005 | Claude adapter and output parser | US-1, US-5 | S-004 | HITL | Handles provider boundary and model-output validation. |
| S-006 | Feature 015 draft node integration | US-1, US-6 | S-005 | HITL | Plugs into durable workflow seam without redefining orchestration. |
| S-007 | Observability and blocked/error outcomes | US-3, US-4, US-7 | S-006 | HITL | Ensures metadata-only traces and final outcome consistency. |

## Slice Details

### S-001: Draft and Claude client contracts
Deliverables: `src\living_adr\core\adr_draft.py`, `src\living_adr\core\llm.py`, `tests\core\test_adr_draft_contract.py`, `tests\core\test_claude_client_fake.py`.
Checkpoint criteria: draft DTO/hash/citations exist; `ClaudeClient` protocol has no SDK types; fake client is deterministic and records calls.

### S-002: LLM policy enforcement
Deliverables: `src\living_adr\workflow\drafting\policy.py`, `tests\workflow\drafting\test_policy.py`.
Checkpoint criteria: denied repositories return `llm_policy_denied`; fake client is not called; metadata contains no prompt/evidence body.

### S-003: Graph context packaging
Deliverables: `src\living_adr\workflow\drafting\context.py`, `tests\workflow\drafting\test_context_packaging.py`.
Checkpoint criteria: only `ArchitectureContextQuery` is used; queries are repository-scoped and bounded; empty context is explicit and safe.

### S-004: Prompt assembly and token budget
Deliverables: `src\living_adr\workflow\drafting\prompt.py`, `src\living_adr\workflow\drafting\token_budget.py`, `tests\workflow\drafting\test_prompt_assembly.py`, `tests\workflow\drafting\test_token_budget.py`.
Checkpoint criteria: required change/evidence included or blocked; optional context truncates deterministically; prompt labels rationale provisional and delimits untrusted text.

### S-005: Claude adapter and output parser
Deliverables: `src\living_adr\workflow\drafting\claude_adapter.py`, `src\living_adr\workflow\drafting\parser.py`, `tests\workflow\drafting\test_claude_adapter.py`, `tests\workflow\drafting\test_draft_parser.py`.
Checkpoint criteria: Anthropic SDK isolated; tests mock SDK/use fakes only; parser rejects missing required ADR sections.

### S-006: Feature 015 draft node integration
Deliverables: `src\living_adr\workflow\nodes\adr_draft.py`, `tests\workflow\test_adr_draft_node.py`, `tests\workflow\test_adr_draft_node_no_mutation.py`.
Checkpoint criteria: node satisfies Feature 015 seam; writes draft content/hash/citations/outcomes; never calls graph mutation, approval, audit, UI, or publish-back.

### S-007: Observability and blocked/error outcomes
Deliverables: `src\living_adr\observability\drafting_events.py`, `tests\observability\test_drafting_events.py`, updates to `tests\workflow\test_adr_draft_node.py`.
Checkpoint criteria: events include safe metadata only; raw prompts/diffs/drafts/responses excluded; all blocked/error outcomes represented consistently.

## Dependency Graph
```text
S-001 ──→ S-002 ──┐
       └→ S-003 ──┴→ S-004 ─→ S-005 ─→ S-006 ─→ S-007
```

## Machine-Readable Slice List
```yaml
slices:
  - id: S-001
    name: Draft and Claude client contracts
    depends_on: []
    task_count: 4
    automation: HITL
    automation_reason: "Establishes DTOs and fake-client seam used by all later work."
  - id: S-002
    name: LLM policy enforcement
    depends_on: [S-001]
    task_count: 2
    automation: HITL
    automation_reason: "Controls external data egress."
  - id: S-003
    name: Graph context packaging
    depends_on: [S-001]
    task_count: 2
    automation: HITL
    automation_reason: "Enforces Feature 007 query-port-only context."
  - id: S-004
    name: Prompt assembly and token budget
    depends_on: [S-002, S-003]
    task_count: 4
    automation: HITL
    automation_reason: "Determines external prompt content and budget behavior."
  - id: S-005
    name: Claude adapter and output parser
    depends_on: [S-004]
    task_count: 4
    automation: HITL
    automation_reason: "Handles provider boundary and model-output validation."
  - id: S-006
    name: Feature 015 draft node integration
    depends_on: [S-005]
    task_count: 4
    automation: HITL
    automation_reason: "Plugs into durable workflow seam without redefining orchestration."
  - id: S-007
    name: Observability and blocked/error outcomes
    depends_on: [S-006]
    task_count: 3
    automation: HITL
    automation_reason: "Ensures metadata-only traces and final outcome consistency."
```

## Context Reset Points
Reset context after S-001, after S-004, and before S-006. Carry forward: Feature 004 exact fields, Feature 007 query-port-only rule, Feature 015 draft seam, deny-before-egress, 8,000 token default, fake-client requirement, and no-mutation boundary.
