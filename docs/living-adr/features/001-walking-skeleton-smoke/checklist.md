# Quality Checklist: walking-skeleton-smoke

## CRISPY Phase Gates

### 🔬 C — Research
- [ ] `research.md` states the target implementation repository was absent and documents that finding.
- [ ] `research.md` is grounded in `..\..\architecture.md` and `..\..\domain-research.md` rather than unimplemented code assumptions.
- [ ] Relevant service boundaries, data model, deployment constraints, and anti-pattern failure modes are cited.
- [ ] External integrations are catalogued and marked stubbed/deferred where applicable.
- [ ] Research preserves the distinction between current state and desired implementation.

### 🎯 R — Sound Intent
- [ ] `intent.md` includes current state, desired state, and gap analysis.
- [ ] At least 3 architecture options were evaluated.
- [ ] Selected approach explains why production-shaped stubs are preferable to a single script or deferral.
- [ ] `intent.md` references `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`, `..\..\architecture.md#deployment`, and `..\..\architecture.md#anti-patterns`.
- [ ] Approval-bound mutation and source-of-truth hierarchy are explicitly preserved.
- [ ] Module surface analysis identifies isolated-test candidates.

### 🍕 I — Vertical Slices
- [ ] `outline.md` contains exactly 5 slices matching the feature-map estimate.
- [ ] Each slice is independently testable with concrete checkpoint criteria.
- [ ] Slice dependency graph is sequential and machine-readable.
- [ ] Every slice includes `automation: HITL | AFK` and `automation_reason`.
- [ ] Automation classifications agree between `outline.md` and `implementation-manifest.yaml`.
- [ ] No slice claims production GitHub, Claude, LlamaIndex, HITL UI, or MCP conformance is complete.

### 📋 S — Tactical Plan
- [ ] `plan.md` references specific file paths for every planned change.
- [ ] New and modified files are clearly distinguished.
- [ ] Plan includes RED test tasks before GREEN implementation tasks.
- [ ] Machine-readable task graph includes TASK-001 through TASK-015.
- [ ] Rollback strategy is documented.
- [ ] No production code is included in planning artifacts.

### 🧹 P — Fresh Context
- [ ] `outline.md` identifies context reset points after SL-002 and SL-004.
- [ ] Each slice lists key files needed in context.
- [ ] State that must carry across slices is explicitly listed.
- [ ] No slice depends on hidden session knowledge outside the artifacts.

### 📝 Y — Task Yield
- [ ] `tasks.md` is organized by user story.
- [ ] Task IDs align with `plan.md` task graph.
- [ ] Every functional task has a paired or preceding test intention.
- [ ] Dependencies between tasks are explicit.
- [ ] Parallel opportunities are identified as intentionally none for first implementation.

### 🧪 No Horizontal Slicing (L3)
- [ ] Tasks are ordered by behavior within each slice: RED tests, then models/implementation.
- [ ] Later-slice tests are not scheduled before earlier behavior is implemented.
- [ ] Reviewers must flag premature abstractions or tests for future behaviors as boundary violations.

## Feature-Specific Quality Gates

### Walking Skeleton Acceptance Coverage
- [ ] US-1 replay acceptance scenarios map to SL-001 and TASK-001..TASK-003.
- [ ] US-2 stub classifier/draft scenarios map to SL-002 and TASK-004..TASK-006.
- [ ] US-3 HITL/persistence scenarios map to SL-003/SL-004 and TASK-007..TASK-012.
- [ ] US-4 MCP-style query scenarios map to SL-005 and TASK-013..TASK-015.
- [ ] Full E2E smoke test demonstrates replay -> classify -> draft -> accept -> persist -> answer.

### Seam Compliance
- [ ] Persistence has a negative test for missing `ApprovedReviewDecision`.
- [ ] MCP-style query reads approved `ADRRecord` context only.
- [ ] `ADRDraft` is never treated as authoritative rationale.
- [ ] Repository identity is present on event, change, draft, decision, record, and query.
- [ ] Stub labels are visible in draft and implementation names.

### Source-Learning Traceability (L1)
- [ ] Domain failure modes FM-06, FM-08, FM-10, FM-13, FM-15, FM-16, FM-17, FM-20, FM-21, and FM-23 are carried into tests or design notes.
- [ ] Public-agent/MCP boundary is documented as read-only.
- [ ] Trace/telemetry raw export is not introduced by this feature.
- [ ] No transcript/caption or external personal-data processing is introduced.

## Pre-Implementation Checks
- [ ] All 8 requested artifacts exist in the feature folder.
- [ ] `implementation-manifest.yaml` has `ready: true` only if no planning blockers remain.
- [ ] Implementation base/current branch identified in affected repos before coding.
- [ ] No repo-wide feature branches were created during planning.
- [ ] Required local Python/uv environment can be set up by implementation.
- [ ] No unresolved open questions in `spec.md` block planning.

## Implementation Checks (per task)
- [ ] Task matches `plan.md`; no scope creep.
- [ ] Tests are written before or alongside implementation.
- [ ] No unrelated files are changed.
- [ ] Code follows architecture patterns from `research.md`.
- [ ] Checkpoint criteria from `outline.md` are met before moving to the next slice.
- [ ] Production external calls remain absent from smoke tests.

## Final Smoke Demonstration Gate
- [ ] Local test command passes.
- [ ] Duplicate replay behavior is verified.
- [ ] Unauthorized mutation attempt is verified.
- [ ] Approved-only MCP-style answer is verified with citation.
- [ ] Summary output can show the created approved `ADRRecord` id and why-answer citation.
