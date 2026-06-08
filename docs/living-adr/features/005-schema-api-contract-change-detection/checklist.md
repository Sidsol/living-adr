# Quality Checklist: schema-api-contract-change-detection

## CRISPY Phase Gates

### 🔬 C — Blind Research

- [x] research.md documents the current scaffold-only codebase objectively.
- [x] Existing directory structure and smoke-test flow are listed with concrete paths.
- [x] No existing schema/API classifier implementation is assumed.
- [x] Integration points are catalogued as planned boundaries, not current code.
- [x] Technical debt items identify scaffold-only gaps and missing shared contracts.

### 🎯 R — Sound Intent

- [x] Gap analysis maps scaffold/current planning state to desired classifier state.
- [x] At least 3 architecture options were evaluated.
- [x] Selected approach has clear rationale tied to `..\..\architecture.md#service-boundaries`, `#data-model`, `#cross-cutting`, and `#anti-patterns`.
- [x] Anti-patterns identify schema/API conflation, magic thresholds, raw diff leakage, and over-broad mining.
- [x] Affected repository is listed with confidence.
- [x] Module Surface Analysis identifies isolated-test candidates.

### 🍕 I — Vertical Slices

- [x] outline.md defines 7 vertical slices.
- [x] Each slice delivers testable behavior with checkpoint criteria.
- [x] Slice dependencies are mapped in text and machine-readable YAML.
- [x] Schema detection and API detection are separate slices/behaviors.
- [x] Every slice includes `automation: HITL | AFK` and `automation_reason`.
- [x] Automation classifications agree between `outline.md` and `implementation-manifest.yaml`.

### 📋 S — Tactical Plan

- [x] Every planned change references a specific file path.
- [x] New files and modified files are clearly distinguished.
- [x] Complexity estimates are provided per phase.
- [x] Rollback strategy is documented.
- [x] `plan.md` includes a machine-readable task graph.

### 🧹 P — Fresh Context

- [x] Context reset points are identified between slices.
- [x] Each slice lists key files needed in context.
- [x] Shared state that must carry across slices is explicitly listed.
- [x] No slice assumes access to production code outside its key files and upstream contracts.

### 📝 Y — Task Yield

- [x] Tasks are organized by user story.
- [x] Task IDs align with the plan task graph.
- [x] Every task is completable in a focused session.
- [x] Dependencies between tasks are explicit.
- [x] Parallel opportunities are identified and limited to non-conflicting detector work.
- [x] Test tasks exist before implementation tasks for each behavior.

### 🧪 No Horizontal Slicing (L3)

- [x] Multi-behavior slices identify distinct behavior sets.
- [x] Tasks are ordered RED → GREEN by behavior.
- [x] Schema and API detector work is not combined into one all-tests/all-implementation phase.
- [x] Reviewers can flag premature abstractions or tests for future behavior as boundary violations.

## Feature-Specific Quality Gates

- [x] Schema vs API semantics are kept distinct in spec, intent, outline, plan, and tasks.
- [x] `StructuralChange` is defined as a common abstraction usable by dependency, schema, and API producers.
- [x] Feature 004 `spec.md` and `intent.md` were read; feature 005 reuses the byte-identical serialized `StructuralChange` / `ChangeEvidence` field set.
- [x] `ChangeEvidence` remains immutable evidence, not inferred rationale.
- [x] Confidence is bounded, explainable, and tied to a threshold policy version.
- [x] Explicit uncertainty is required for generated artifacts, runtime/dynamic patterns, and static-analysis blind spots.
- [x] Low-confidence/no-ADR-needed outcomes are retained for tuning instead of silently discarded.
- [x] Threshold decision OQ-005-1 is resolved as configurable `semantic-change-default-v1` default `0.70` with per-repository overrides.
- [x] Metadata-only observability excludes raw diffs, source snippets, prompts, secrets, and reviewer/model content.

## Source-Learning Traceability

- [x] FM-03 ADR fatigue/threshold control is referenced.
- [x] FM-06 provisional rationale separation is referenced.
- [x] FM-07 static graph blind spots are referenced and handled with uncertainty notes.
- [x] FM-18 minimal evidence fetching is referenced.
- [x] FM-19 PR-summary overtrust is avoided by using PR/diff evidence, not summaries alone.
- [x] FM-21 trace leakage is handled through metadata-only observability.
- [x] Public-agent boundary is preserved: classifier output cannot mutate graph or become authoritative without HITL.

## Pre-Implementation Checks

- [x] All eight requested planning artifacts exist in this feature folder.
- [x] No production code was modified during planning.
- [x] No files outside this feature folder were modified during planning.
- [x] Confidence threshold decision OQ-005-1 is resolved: default `0.70`, configurable per repository, below-threshold evidence retained.
- [ ] Feature 003 `SCMEvent` and evidence contracts are implemented or stable enough for integration.
- [x] Feature 004 shared `StructuralChange` / `ChangeEvidence` contract was checked from `spec.md` and `intent.md`.
- [ ] Implementation base/current branch identified in `C:\repos\living-adr`.
- [ ] Development environment verification command selected: `uv run pytest` and `uv run ruff check`.

## Implementation Checks (per task)

- [ ] Task matches the plan — no scope creep.
- [ ] Tests written before or alongside implementation.
- [ ] No unrelated changes included.
- [ ] Code follows existing/planned patterns from research.md and architecture.md.
- [ ] Checkpoint criteria from outline.md are met.
- [ ] Schema/API outputs use feature 004's byte-identical serialized `StructuralChange` contract.
- [ ] Uncertainty notes are present for generated/runtime-limited evidence.
- [ ] Threshold policy version and numeric threshold are recorded on classifier outputs.
