# Codebase Research: claude-adr-drafting-capability

## Research Basis
LivingADR is greenfield in the inherited CRISPY artifacts; no production implementation was inspected or modified. Findings are grounded in:

- `..\..\vision.md`
- `..\..\domain-research.md`
- `..\..\architecture.md`
- `..\..\feature-map.md`
- `..\..\roadmap.md`
- `..\004-dependency-change-detection\spec.md` and `intent.md`
- `..\007-llamaindex-property-graph-adapter\spec.md` and `intent.md`
- `..\015-workflow-orchestration-checkpointing\spec.md` and `intent.md`

## Project Shape
The planned implementation repository is a single Python repo, `living-adr`, with two deployables: workflow-service and MCP context server. Feature 008 belongs to workflow-service only. Relevant planned folders from `architecture.md#tech-stack` are:

```text
src\living_adr\core
src\living_adr\workflow
src\living_adr\workflow\nodes
src\living_adr\graph
tests\core
tests\workflow
tests\observability
```

## Feature 008 Position in Roadmap
Feature-map entry 008 is `claude-adr-drafting-capability`, high complexity, ~7 slices, depending on 004, 007, and 015. Roadmap Wave W3 places it after the dependency classifier, graph adapter, and workflow backbone. Its role is the first end-to-end ADR draft generation capability, not approval or mutation.

## Dependency Findings

### Feature 004: dependency change detection
Feature 004 produces the exact `StructuralChange` and immutable `ChangeEvidence` records consumed here. The intent explicitly says Feature 008 can consume these records without live SCM calls or raw GitHub payloads. Evidence proves what changed; it is not authoritative rationale.

### Feature 007: graph context adapter
Feature 007 implements the default `ArchitectureContextQuery` adapter over LlamaIndex. Feature 008 must depend only on the query port and domain DTOs (`answer_why`, `traverse_from_code_area`, `fetch_adr`, `list_adrs`, snapshot validation), never on LlamaIndex internals or graph write ports.

### Feature 015: workflow orchestration/checkpointing
Feature 015 owns LangGraph topology, SQLite checkpointing, HITL interrupt/resume, replay, and mutation handoff. It defines a draft-node seam: `ADRDraftNode.__call__(state: WorkflowState) -> WorkflowState`. Feature 008 replaces/stabilizes the stub behind this seam and must not redefine workflow state, checkpointer, or HITL contracts.

## Logic Flow
1. Feature 015 workflow reaches draft node after structural classification.
2. Node selects a Feature 004 dependency `StructuralChange` where `adr_recommendation="draft"`.
3. Node resolves linked `ChangeEvidence` already present in workflow state.
4. Repository LLM policy is checked before external prompt egress.
5. If denied, node returns a typed policy-blocked outcome and emits safe metadata only.
6. If allowed, node queries `ArchitectureContextQuery` for approved context/citations.
7. Prompt assembler creates delimited sections: change, evidence, context, ADR format, constraints, provisional-label instructions.
8. Token budgeter includes required evidence or blocks; optional context truncates deterministically.
9. `ClaudeClient` adapter is invoked; tests use `FakeClaudeClient` only.
10. Parser validates required ADR sections and produces provisional draft + hash + metadata.
11. Feature 015 routes draft to HITL; no persistence/mutation occurs here.

## Planned Modules
| Module | Responsibility |
|---|---|
| `core\adr_draft.py` | Provisional draft DTO, draft record candidate, citations, content hash. |
| `core\llm.py` | `ClaudeClient` protocol, request/response/error models, fake client. |
| `workflow\drafting\policy.py` | Repository external-LLM allow/deny gate. |
| `workflow\drafting\context.py` | Query-port context packaging and citation normalization. |
| `workflow\drafting\token_budget.py` | Deterministic budget estimation, truncation, blocking. |
| `workflow\drafting\prompt.py` | ADR prompt assembly with anti-injection delimiters. |
| `workflow\drafting\claude_adapter.py` | Anthropic SDK wrapper behind `ClaudeClient`. |
| `workflow\drafting\parser.py` | Markdown ADR validation/parsing. |
| `workflow\nodes\adr_draft.py` | Feature 015-compatible real draft node. |
| `observability\drafting_events.py` | Safe metadata-only event builders. |

## Anti-Pattern Pressure
- FM-04/Fake rationale: drafts must label inferred rationale as provisional.
- FM-06/Hallucinated rationale: approved graph citations and evidence citations are required.
- FM-14/Prompt injection: repository text is delimited and cannot issue tool/mutation instructions.
- FM-19/PR-summary overtrust: use Feature 004 evidence, not PR prose, as primary input.
- FM-21/Trace leakage: raw prompts/drafts/diffs/responses are excluded by default.

## Test Strategy Findings
Use pytest with fake clients, fake graph query, fake workflow state, and SDK mocks. Required checks: policy-deny no-call, budget block no-call, context query port-only, prompt golden assertions, parser required sections, draft-node seam fields, no-mutation boundary, and telemetry redaction.

## Open Research Items Resolved by Defaults
- Token budget: default 8,000 prompt tokens, configurable.
- Claude model: configurable, default `claude-sonnet-4-6`.
- Empty graph context: drafting may proceed with explicit no-approved-context marker and provisional label.
- Missing required evidence: block drafting rather than fetching SCM directly.
