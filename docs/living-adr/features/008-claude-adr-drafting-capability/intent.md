# Architecture Intent: claude-adr-drafting-capability

## Current State
LivingADR is planned but not implemented. Feature 004 defines dependency `StructuralChange` and `ChangeEvidence`. Feature 007 provides the graph query implementation behind `ArchitectureContextQuery`. Feature 015 provides the LangGraph workflow backbone and a draft-node seam. Feature 008 must supply Claude-backed drafting inside that seam.

Architecture anchors:
- `..\..\architecture.md#service-boundaries`: workflow-service owns Claude calls; MCP is read-only; approved mutation happens after HITL.
- `..\..\architecture.md#data-model`: `StructuralChange`, `ChangeEvidence`, `ADRDraft`, `ADRRecord`, approval, and audit boundaries.
- `..\..\architecture.md#tech-stack`: Python 3.12, LangGraph, Anthropic SDK, fakeable ports, pytest/Ruff/uv.
- `..\..\architecture.md#cross-cutting`: external LLM egress, token budgets, allow/deny policy, metadata-only traces.
- `..\..\architecture.md#anti-patterns`: hallucinated rationale, prompt injection, trace leakage, PR-summary overtrust.
- `..\..\architecture.md#deployment`: local PoC, no unnecessary distributed service split.
- `..\..\architecture.md#repositories`: single `living-adr` repository.

## Desired State
A production-ready planning target where the workflow service has a real `ADRDraftNode` that consumes Feature 004 contracts, queries Feature 007 context, enforces repository LLM policy, packages prompts within budget, calls Claude through a fakeable adapter, validates output into a provisional draft, emits metadata-only telemetry, and hands back to Feature 015 for HITL.

## Options Considered

### Option A — Inline Anthropic calls in the node
Pros: fastest prototype. Cons: hard to test, easy to bypass policy/budget, Anthropic SDK leaks into workflow, violates swappable-port philosophy. Rejected.

### Option B — Separate drafting microservice
Pros: egress isolation and independent scaling. Cons: overbuilt for local PoC, adds auth/deployment/retry complexity, conflicts with `#deployment` simplicity. Rejected.

### Option C — Domain-first node with adapter ports (selected)
Pros: preserves Feature 015 seam, keeps Claude swappable/fakeable, enforces policy and budget centrally, uses query-port-only graph context, and avoids authoritative mutation. Cons: more modules/tests than inline implementation. Selected.

### Option D — Deterministic template-only drafts
Pros: no egress, deterministic. Cons: fails Claude ADR drafting capability and reduces value for alternatives/consequences synthesis. Rejected.

## Selected Approach
Implement a domain-first `ADRDraftNode` composed of small services: policy evaluator, graph context packer, prompt assembler, token budgeter, `ClaudeClient`, parser, draft DTO/hash helper, and safe telemetry builder. The node satisfies Feature 015's `ADRDraftNode.__call__(state: WorkflowState) -> WorkflowState` seam and does not redefine orchestration.

## Module Surface
| Module | Purpose | Test seam |
|---|---|---|
| `src\living_adr\core\adr_draft.py` | Provisional draft DTO, citations, hash | Pure unit tests |
| `src\living_adr\core\llm.py` | `ClaudeClient` protocol and fake | Fake call assertions |
| `src\living_adr\workflow\drafting\policy.py` | External LLM allow/deny | Pure policy tests |
| `src\living_adr\workflow\drafting\context.py` | `ArchitectureContextQuery` packaging | Fake query tests |
| `src\living_adr\workflow\drafting\token_budget.py` | Budget/truncation/blocking | Deterministic unit tests |
| `src\living_adr\workflow\drafting\prompt.py` | Delimited prompt assembly | Golden prompt tests |
| `src\living_adr\workflow\drafting\claude_adapter.py` | Anthropic SDK wrapper | Mock SDK tests only |
| `src\living_adr\workflow\drafting\parser.py` | Markdown ADR validation | Parser tests |
| `src\living_adr\workflow\nodes\adr_draft.py` | Feature 015 seam integration | Fake state/client/query tests |
| `src\living_adr\observability\drafting_events.py` | Metadata-only events | Redaction tests |

## Contract Bindings
- **Feature 004:** consume `StructuralChange` and `ChangeEvidence` exactly; do not mutate, extend required fields, or fetch raw SCM data.
- **Feature 007:** call `ArchitectureContextQuery` only; no LlamaIndex/store/write-port imports.
- **Feature 015:** implement the draft node only; do not redefine `WorkflowState`, checkpointer, HITL interrupt/resume, replay, mutation handoff, or graph topology.

## Anti-Patterns to Avoid
- Treating Claude output as authoritative.
- Allowing model/tool calls to mutate graph, GitHub, audit, or approval state.
- Building prompts before policy approval.
- Logging raw prompts, diffs, Claude responses, or pre-approval drafts.
- Querying graph internals instead of `ArchitectureContextQuery`.
- Using PR prose as primary evidence instead of Feature 004 evidence.
- Letting normal tests call real Anthropic APIs.

## Affected Repositories
| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add workflow-service drafting modules, fakeable Claude adapter, prompt budget/context services, draft node, telemetry helpers, and tests. | High |

## Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Hallucinated rationale appears approved | Medium | High | Provisional labels, citations, HITL-only authority. |
| LLM policy bypass leaks data | Low | High | Gate before prompt/client; tests assert no call on deny. |
| Budget truncates critical evidence | Medium | Medium | Required evidence cannot be truncated; block instead. |
| Prompt injection | Medium | High | Delimit repository text; no tools/mutations; instruction hierarchy. |
| Feature 015 seam drift | Medium | High | Seam tests; no topology/checkpointer changes. |
| Raw trace leakage | Medium | High | Central safe event builder; redaction tests. |
| Anthropic SDK/model changes | Medium | Medium | Isolate SDK; configurable model id; fake tests. |
