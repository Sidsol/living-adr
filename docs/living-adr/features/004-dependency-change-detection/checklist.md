# Quality Checklist: dependency-change-detection

## CRISPY Phase Gates

### 🔬 C — Blind Research
- [x] Research documents greenfield current state without production code assumptions.
- [x] `research.md` identifies planned architecture, directories, logic flows, data models, and integration points.
- [x] Feature 003 evidence contract is captured as an upstream dependency.
- [x] Technical debt/open questions are noted with project-artifact references.

### 🎯 R — Sound Intent
- [x] `intent.md` references `..\..\architecture.md#service-boundaries`.
- [x] `intent.md` references `..\..\architecture.md#data-model`.
- [x] `intent.md` references `..\..\architecture.md#cross-cutting`.
- [x] `intent.md` references `..\..\architecture.md#anti-patterns`.
- [x] Gap analysis maps current planned state to desired dependency classifier state.
- [x] At least 3 architecture options were evaluated.
- [x] Selected approach has clear rationale.
- [x] Anti-patterns are identified with explanations.
- [x] Affected repositories are listed with confidence levels.
- [x] Module Surface Analysis identifies isolated-test candidates.

### 🍕 I — Vertical Slices
- [x] `outline.md` defines 5 slices matching feature-map estimate.
- [x] Each slice delivers end-to-end testable functionality.
- [x] Slice dependencies are mapped and ordered correctly.
- [x] Context management boundaries are defined.
- [x] Every slice includes `automation: HITL | AFK` and `automation_reason`.
- [x] Automation classifications agree between `outline.md` and `implementation-manifest.yaml`.

### 📋 S — Tactical Plan
- [x] Every implementation step references a specific file path.
- [x] New files and modified files are clearly distinguished.
- [x] Complexity estimates are provided per phase.
- [x] Rollback strategy is documented.
- [x] `plan.md` includes machine-readable `task_graph`.

### 🧹 P — Fresh Context
- [x] Context reset points are identified between slices.
- [x] Each slice lists key files needed in context.
- [x] Shared state that must carry across slices is explicit.

### 📝 Y — Task Yield
- [x] Tasks are organized by user story.
- [x] Task IDs are unique and aligned with `plan.md` task graph.
- [x] Every task is sized for a focused session.
- [x] Dependencies between tasks are explicit.
- [x] Test tasks exist for each functional behavior.

### 🧪 No Horizontal Slicing (L3)
- [x] Each slice groups tests and implementation by behavior.
- [x] RED→GREEN ordering is preserved in `tasks.md`.
- [x] No slice contains future behavior tests unrelated to that slice.

## Feature-Specific Pre-Implementation Gates

- [x] `StructuralChange` produced for Feature 008 is defined with repository, event ids, confidence, source paths, evidence ids, and recommendation.
- [x] Immutable `ChangeEvidence` produced for Feature 008 is defined with source path, provenance, parser metadata, immutable hash, and safe summary.
- [x] Below-threshold path emits no-ADR-needed outcomes rather than silently dropping evidence.
- [x] Classification is deterministic and testable without live GitHub, Claude, graph store, or LangGraph runtime.
- [x] Direct dependency manifest changes are distinguished from lockfile-only/transitive churn.
- [x] Metadata-only observability excludes raw diffs and file contents.
- [x] Feature scope excludes schema/API classifiers, Claude drafting, HITL approval, and graph mutation.

## Pre-Implementation Checks

- [x] All requested planning artifacts are present: `spec.md`, `research.md`, `intent.md`, `outline.md`, `plan.md`, `tasks.md`, `checklist.md`, `implementation-manifest.yaml`.
- [x] No files outside `features\004-dependency-change-detection\` are modified by this planning run.
- [x] No production code is created by this planning run.
- [x] No unresolved open question blocks implementation; default confidence threshold is documented as configurable.

## Implementation Checks (per task)

- [ ] Task matches the plan — no scope creep.
- [ ] Tests written before or alongside implementation.
- [ ] No unrelated changes included.
- [ ] Code follows existing patterns from `research.md` and architecture anchors.
- [ ] Checkpoint criteria from `outline.md` are met.
- [ ] Raw diffs, full dependency file contents, secrets, prompts, and reviewer comments are not exported to observability.
- [ ] No draft-eligible `StructuralChange` is emitted for below-threshold no-ADR-needed outcomes.
