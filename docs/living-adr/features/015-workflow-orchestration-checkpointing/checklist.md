# Quality Checklist: workflow-orchestration-checkpointing

## CRISPY Phase Gates

### 🔬 C — Research
- [ ] `research.md` cites `..\..\architecture.md#tech-stack` for LangGraph ownership of workflow/state-machine orchestration.
- [ ] `research.md` distinguishes LangGraph checkpoint state from feature 003 ingestion replay, feature 010 approval/audit durability, and feature 007 graph persistence.
- [ ] LangGraph interrupt/resume and SQLite checkpointer findings are documented.
- [ ] FM-01 and FM-17 replay/recovery risks are explicitly referenced.
- [ ] Dependency contracts from feature 003 and feature 006 are summarized.

### 🎯 R — Sound Intent
- [ ] Gap analysis maps current architecture/dependencies to desired workflow graph/checkpointer state.
- [ ] At least 3 architecture options were evaluated.
- [ ] Selected approach references `..\..\architecture.md#tech-stack`, `#service-boundaries`, `#data-model`, `#cross-cutting`, and `#anti-patterns`.
- [ ] Module Surface Analysis lists workflow state, protocols, graph, checkpointer, resume, replay, and tests.
- [ ] Anti-patterns explicitly prevent overlap with feature 009 UI and feature 010 approval/audit durability.

### 🍕 I — Vertical Slices
- [ ] Outline contains exactly 6 slices.
- [ ] Each slice delivers end-to-end testable behavior.
- [ ] Slice dependencies are mapped in prose and machine-readable YAML.
- [ ] Every slice includes `automation: HITL` and `automation_reason`.
- [ ] Automation classifications agree between `outline.md` and `implementation-manifest.yaml`.
- [ ] No slice requires production classifier, Claude draft, HITL UI, approval audit, graph adapter, or MCP implementation.

### 📋 S — Tactical Plan
- [ ] Every implementation step references a specific relative path from `living-adr` repo root.
- [ ] New files and modified files are clearly distinguished.
- [ ] Plan includes `task_graph` YAML with TASK-001 through TASK-019.
- [ ] Complexity estimates are provided per phase.
- [ ] Rollback strategy is documented per phase.
- [ ] Dependency validation for LangGraph SQLite checkpointer is explicit before package changes.

### 🧹 P — Fresh Context
- [ ] Context reset points are identified after Slice 1 and after Slice 4.
- [ ] Each slice lists key files needed in context.
- [ ] State carried across slices is limited to node seams, thread id rule, mutation boundary, and WAL constraints.

### 📝 Y — Task Yield
- [ ] Tasks are organized by user story.
- [ ] Task IDs align with `plan.md` task graph.
- [ ] Every functional task has an associated test task.
- [ ] Dependencies between tasks are explicit in execution order.
- [ ] Parallel opportunities are intentionally conservative and documented.
- [ ] Every task is completable in less than one focused session.

### 🧪 No Horizontal Slicing (L3)
- [ ] Tasks are ordered by behavior: state, protocols/stubs, checkpointing, graph, resume, mutation boundary, replay.
- [ ] Tests are paired with their behavior before moving to the next behavior.
- [ ] No phase implements all tests first or all production files first across multiple behaviors.

## Feature-Specific Pre-Implementation Checks
- [ ] Graph can be assembled with stub nodes before features 008/009/010 exist.
- [ ] SQLite checkpointer persists in-flight state and supports restart recovery.
- [ ] HITL interrupt/resume is verified with the same deterministic `thread_id`.
- [ ] Replay/recovery is testable from feature 003 normalized event contracts.
- [ ] Single-writer + WAL rule is preserved; workflow-service is the only writer.
- [ ] `ApprovalBoundMutationService` is the only mutation handoff target.
- [ ] Node seams are documented for 008 classifier/draft plug-in, 009 UI resume plug-in, and 010 approval/audit capability plug-in.
- [ ] No code path requires raw GitHub payloads inside graph state.
- [ ] Observability remains metadata-only by default; raw diffs, prompts, drafts, and reviewer comments are not exported.

## Source-Learning Traceability
- [ ] FM-01 mitigation: replayable event-to-workflow path is included in spec/outline/plan.
- [ ] FM-17 mitigation: duplicate/gap/replay behavior is included in tests and task graph.
- [ ] FM-13/FM-23 mitigation: mutation requires approval-bound handoff and no direct graph writes.
- [ ] Public-agent boundary is preserved: no MCP server write capability is introduced.
- [ ] Transcript/caption limitations are not applicable to this feature and no media-processing assumptions are introduced.

## Implementation Checks (per task)
- [ ] Task matches plan with no scope creep into production classifier, drafting, UI, approval durability, graph adapter, publish-back, MCP, or LangSmith dashboards.
- [ ] Tests are written before or alongside implementation.
- [ ] No unrelated files are changed.
- [ ] Code follows existing patterns from dependency features.
- [ ] Checkpoint criteria from `outline.md` are met before marking the slice complete.
