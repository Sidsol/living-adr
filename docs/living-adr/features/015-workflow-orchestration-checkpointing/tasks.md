# Task Breakdown: workflow-orchestration-checkpointing

## Legend
- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ⬜ Not started | 🔵 In progress | ✅ Done | ❌ Blocked

## Tasks by Story

### US-1: Assemble the durable workflow graph

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | Create `WorkflowState` and workflow status models. | ✅ | Slice 1; prerequisite for all nodes. |
| TASK-002 | P1 | Write RED→GREEN tests for workflow state validation and sensitive payload exclusion. | ✅ | Tests for TASK-001 behavior. |
| TASK-003 | P1 | Create node Protocol definitions for intake, classifier, draft, HITL, and mutation seams. | ✅ | Documents 008/009/010 contracts. |
| TASK-004 | P1 | Implement deterministic stub classifier, draft, HITL, and mutation handoff nodes. | ✅ | Depends on TASK-003. |
| TASK-005 | P1 | Write protocol/stub tests proving stable node seam behavior. | ✅ | Tests TASK-003/TASK-004. |
| TASK-009 | P1 | Build LangGraph graph assembly and routing with injected nodes. | ✅ | Depends on checkpointer setup. |
| TASK-010 | P1 | Export graph/checkpoint APIs from workflow package without app imports. | ✅ | Depends on TASK-009. |
| TASK-011 | P1 | Write graph execution tests for intake→classify→draft→HITL and no-ADR terminal path. | ✅ | Tests TASK-009/TASK-010. |

### US-2: Persist in-flight workflow state

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-006 | P1 | Validate LangGraph SQLite checkpointer dependency and update `pyproject.toml` only if needed. | ✅ | Must run before implementing factory. |
| TASK-007 | P1 | Implement SQLite checkpointer factory with WAL mode and busy timeout. | ✅ | Keeps SQLite details isolated. |
| TASK-008 | P1 | Write checkpoint persistence tests across separate graph/checkpointer instances. | ✅ | Tests TASK-007. |

### US-3: Interrupt for HITL and resume safely

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-012 | P1 | Implement review start/resume service with deterministic `thread_id` derivation. | ✅ | Depends on graph assembly. |
| TASK-013 | P1 | Add workflow-service internal hook seam for start/resume/replay callers. | ✅ | No UI rendering. |
| TASK-014 | P1 | Write resume tests for approve, approve-after-edit, reject, defer, wrong-thread, and restart scenarios. | ✅ | Tests TASK-012/TASK-013. |

### US-4: Support replay and recovery from intake failures

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-017 | P1 | Implement orchestration replay bridge from feature 003 stored events into graph threads. | ✅ | Depends on mutation boundary. |
| TASK-018 | P1 | Wire replay into the workflow-service internal hook seam. | ✅ | Shares `workflow_routes.py` with TASK-013. |
| TASK-019 | P1 | Write replay/recovery tests for duplicate replay, pending HITL recovery, and no duplicate side effects. | ✅ | Tests TASK-017/TASK-018. |

### US-5: Preserve graph mutation and audit boundaries

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-015 | P1 | Implement mutation handoff behavior that calls `ApprovalBoundMutationService` only with approved capability. | ✅ | No capability minting/audit durability. |
| TASK-016 | P1 | Write mutation boundary tests for no-call and exactly-once service-call cases. | ✅ | Include import-boundary assertion. |

## Infrastructure / Cross-Cutting Checks

- TASK-006 must confirm dependency/package compatibility before changing `pyproject.toml`; do not add a package unless required.
- TASK-007 must preserve single-writer SQLite WAL behavior; workflow-service remains the only writer.
- TASK-013 must keep app hooks internal and UI-free; feature 009 owns reviewer UI.

## Execution Order
1. **Sequential behavior A:** TASK-001 → TASK-002.
2. **Sequential behavior B:** TASK-003 → TASK-004 → TASK-005.
3. **Sequential behavior C:** TASK-006 → TASK-007 → TASK-008.
4. **Sequential behavior D:** TASK-009 → TASK-010 → TASK-011.
5. **Sequential behavior E:** TASK-012 → TASK-013 → TASK-014.
6. **Sequential behavior F:** TASK-015 → TASK-016.
7. **Sequential behavior G:** TASK-017 → TASK-018 → TASK-019.

## Parallel Opportunities
- None recommended for first implementation pass. Although TASK-002 and TASK-003 touch different files, the state shape is foundational and should settle before protocols/stubs are finalized.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 19 | ~24-32 hours |
| P2 | 0 | 0 |
| P3 | 0 | 0 |
