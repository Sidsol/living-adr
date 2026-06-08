# CRISPY Quality Checklist: claude-adr-drafting-capability

## Planning Artifact Gates
- [x] `spec.md` created with requirements, scope, out-of-scope, acceptance criteria, and autopilot defaults.
- [x] `research.md` created from inherited artifacts and dependency contracts.
- [x] `intent.md` references `..\..\architecture.md#service-boundaries`.
- [x] `intent.md` references `..\..\architecture.md#data-model`.
- [x] `intent.md` references `..\..\architecture.md#tech-stack`.
- [x] `intent.md` references `..\..\architecture.md#cross-cutting`.
- [x] `intent.md` references `..\..\architecture.md#anti-patterns`.
- [x] `intent.md` references `..\..\architecture.md#deployment`.
- [x] `intent.md` references `..\..\architecture.md#repositories`.
- [x] `intent.md` evaluates at least 3 options and selects one.
- [x] `outline.md` defines 7 independently testable slices.
- [x] `plan.md` defines file-level tactical steps and machine-readable task graph.
- [x] `tasks.md` is story-organized and consistent with plan/outline.
- [x] `implementation-manifest.yaml` is ready with `ready: true`.

## Dependency Contract Gates
- [x] Feature 004 `StructuralChange` contract is copied byte-for-byte in `spec.md` and consumed, not redefined.
- [x] Feature 004 `ChangeEvidence` contract is copied byte-for-byte in `spec.md` and consumed, not redefined.
- [x] Feature 007 graph context is consumed only through `ArchitectureContextQuery`.
- [x] Feature 015 node seam is used without redefining workflow topology, checkpointer, HITL interrupt/resume, or mutation handoff.

## Feature-Specific Gates
- [x] Per-repository `external_llm_allowed` is enforced before Claude egress.
- [x] Token budget default is documented as 8,000 prompt tokens and configurable.
- [x] Fake-client seam ensures tests never call Anthropic by default.
- [x] Prompt assembly includes Feature 004 evidence, graph citations, ADR template, and anti-injection delimiters.
- [x] Claude output is provisional and non-authoritative.
- [x] Metadata-only observability excludes raw prompts, raw diffs, full Claude responses, and full pre-approval drafts.
- [x] No authoritative mutation, approval, audit durability, graph write, GitHub publication, or MCP serving is in scope.

## Consistency Gates
- [x] Slice count is 7 across `outline.md`, `plan.md`, `tasks.md`, and `implementation-manifest.yaml`.
- [x] Task count is 23 across `plan.md`, `tasks.md`, and `implementation-manifest.yaml`.
- [x] Task IDs are unique: TASK-001 through TASK-023.
- [x] All YAML blocks use Windows-style paths.
- [x] No blocking open questions remain; autopilot assumptions are documented.
- [x] No production/application code was written by this planning run.

## Implementation Gates (for later)
- [ ] Run `uv run ruff check` once implementation exists.
- [ ] Run `uv run pytest` once implementation exists.
- [ ] Verify policy-deny path makes zero Claude calls.
- [ ] Verify budget-block path makes zero Claude calls.
- [ ] Verify fake-client seam prevents real API calls in normal tests.
- [ ] Verify draft node never invokes mutation, approval, audit, UI, or publish-back ports.
