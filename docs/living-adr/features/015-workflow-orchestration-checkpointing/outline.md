# Implementation Outline: workflow-orchestration-checkpointing

## Slice Strategy
The feature is decomposed around independently verifiable workflow behaviors: state/seams, durable checkpoint setup, graph execution, HITL resume, mutation safety, and replay/recovery. Each slice is small enough to implement with stubs and tests before production classifier, drafter, UI, or approval durability features arrive.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| 1 | State and node seam contracts | US-1, US-5 | M | — | false | HITL | Defines safety-critical interfaces consumed by 008/009/010. |
| 2 | SQLite checkpointer factory | US-2 | M | 1 | false | HITL | Touches durable state and single-writer/WAL persistence. |
| 3 | Stub graph assembly | US-1 | M | 1, 2 | false | HITL | Establishes production workflow topology and routing. |
| 4 | HITL interrupt/resume service | US-3 | M | 3 | false | HITL | Human-gate semantics and resume safety require review. |
| 5 | Mutation handoff boundary | US-5 | M | 4 | false | HITL | Protects authoritative graph mutation boundary. |
| 6 | Replay/recovery integration | US-4 | M | 3, 4, 5 | false | HITL | Coordinates idempotency, replay, and checkpoint recovery. |

## Slices

### Slice 1: State and node seam contracts
**Scope:** Define the typed workflow state, interrupt/resume payloads, node protocols, and deterministic stub node classes.
**User Stories:** US-1, US-5
**Automation:** HITL
**Automation Reason:** Defines safety-critical interfaces consumed by 008/009/010.

**Deliverables:**
- `src\living_adr\workflow\state.py` with `WorkflowState`, `ReviewRequestPayload`, `ReviewResumeCommand`, `WorkflowReplayMetadata`.
- `src\living_adr\workflow\nodes\protocols.py` with classifier, draft, HITL, and mutation node protocols.
- `src\living_adr\workflow\nodes\stubs.py` with deterministic test/local stubs.
- Unit tests for state validation and protocol compatibility.

**Checkpoint Criteria:**
- [ ] State carries repository identity, event key, classification, draft, HITL, decision, mutation, error, and replay fields.
- [ ] Protocols explicitly document what features 008/009/010 implement.
- [ ] Stub nodes can be invoked without GitHub, Claude, UI, or graph adapter.

**Context Notes:**
- Key files: `core\scm.py`, `core\graph\approval_bound_mutation.py`, `workflow\state.py`.
- Dependencies: features 003 and 006 contracts available.
- Estimated complexity: Medium.

### Slice 2: SQLite checkpointer factory
**Scope:** Add the durable checkpointer creation and SQLite WAL/busy-timeout setup for workflow-service-owned state.
**User Stories:** US-2
**Automation:** HITL
**Automation Reason:** Touches durable state and single-writer/WAL persistence.

**Deliverables:**
- `src\living_adr\workflow\checkpointing.py` with checkpointer factory and setup validation.
- Settings integration for workflow checkpoint DB path.
- SQLite integration tests for WAL mode and restart reload.

**Checkpoint Criteria:**
- [ ] Checkpointer path defaults under workflow-service state storage.
- [ ] WAL and busy timeout are configured during setup.
- [ ] Tests verify state persists across separate graph/checkpointer instances.

**Context Notes:**
- Key files: `workflow\checkpointing.py`, project settings module, pytest fixtures.
- Dependencies: Slice 1 state model.
- Estimated complexity: Medium.

### Slice 3: Stub graph assembly
**Scope:** Compile the production LangGraph state machine with stub nodes and deterministic routing.
**User Stories:** US-1
**Automation:** HITL
**Automation Reason:** Establishes production workflow topology and routing.

**Deliverables:**
- `src\living_adr\workflow\graph.py` graph builder.
- Tests for intake → classify → draft → HITL interrupt order.
- Tests for no-ADR-needed terminal routing.

**Checkpoint Criteria:**
- [ ] Graph compiles with injected stubs and checkpointer.
- [ ] A normalized event reaches HITL interrupt with expected payload.
- [ ] No-ADR path terminates without draft or mutation call.

**Context Notes:**
- Key files: `workflow\graph.py`, `workflow\nodes\stubs.py`.
- Dependencies: Slices 1 and 2.
- Estimated complexity: Medium.

### Slice 4: HITL interrupt/resume service
**Scope:** Provide workflow-service callable APIs to start/resume graph threads using typed review commands.
**User Stories:** US-3
**Automation:** HITL
**Automation Reason:** Human-gate semantics and resume safety require review.

**Deliverables:**
- `src\living_adr\workflow\review_resume.py` start/resume service.
- Optional `src\living_adr\apps\workflow_service\workflow_routes.py` local internal route/handler seam.
- Tests for approve, approve-after-edit, reject, and defer resume commands.

**Checkpoint Criteria:**
- [ ] Pending HITL checkpoint can be resumed after simulated restart.
- [ ] Resume requires same deterministic `thread_id` or event-derived identity.
- [ ] Reject/defer do not route to mutation handoff.

**Context Notes:**
- Key files: `workflow\review_resume.py`, `apps\workflow_service\workflow_routes.py`.
- Dependencies: Slice 3.
- Estimated complexity: Medium.

### Slice 5: Mutation handoff boundary
**Scope:** Implement mutation handoff routing that calls `ApprovalBoundMutationService` only when approved capability is present.
**User Stories:** US-5
**Automation:** HITL
**Automation Reason:** Protects authoritative graph mutation boundary.

**Deliverables:**
- Mutation handoff node implementation or stub in `workflow\nodes\stubs.py` / dedicated module.
- Boundary tests with fake mutation service and fake graph store.
- Import-boundary test preventing direct `ArchitectureGraphStore` writes from workflow nodes.

**Checkpoint Criteria:**
- [ ] Missing/rejected/deferred decisions produce no graph mutation call.
- [ ] Approved state calls `ApprovalBoundMutationService` exactly once.
- [ ] Workflow nodes do not import concrete graph adapters or LlamaIndex.

**Context Notes:**
- Key files: `core\graph\approval_bound_mutation.py`, `workflow\nodes\stubs.py`.
- Dependencies: Slice 4 and feature 006.
- Estimated complexity: Medium.

### Slice 6: Replay/recovery integration
**Scope:** Bridge feature 003 replay inputs into deterministic graph start/resume and validate recovery after failures/restarts.
**User Stories:** US-4
**Automation:** HITL
**Automation Reason:** Coordinates idempotency, replay, and checkpoint recovery.

**Deliverables:**
- `src\living_adr\workflow\replay.py` orchestration replay service.
- Tests for replaying a stored normalized event, recovering failed node state, and avoiding duplicate mutation/review side effects.
- Documentation comments in node seam docstrings for replay ownership.

**Checkpoint Criteria:**
- [ ] Replay derives same thread id for the same repository/event key.
- [ ] Failed or interrupted state can be resumed from persisted checkpoint.
- [ ] Duplicate replay does not duplicate mutation service calls.

**Context Notes:**
- Key files: `workflow\replay.py`, feature 003 ingestion replay contracts.
- Dependencies: Slices 3–5.
- Estimated complexity: Medium.

## Slice Dependency Graph
```text
Slice 1 ──→ Slice 2 ──→ Slice 3 ──→ Slice 4 ──→ Slice 5 ──→ Slice 6
Slice 1 ───────────────→ Slice 3
Slice 3 ─────────────────────────────→ Slice 6
Slice 4 ─────────────────────────────→ Slice 6
```

## Slice Dependency Graph (Machine-Readable)

```yaml
slices:
  - id: 1
    name: State and node seam contracts
    depends_on: []
    parallelizable: false
    automation: HITL
    automation_reason: "Defines safety-critical interfaces consumed by 008/009/010."
    checkpoint_criteria_count: 3
  - id: 2
    name: SQLite checkpointer factory
    depends_on: [1]
    parallelizable: false
    automation: HITL
    automation_reason: "Touches durable state and single-writer/WAL persistence."
    checkpoint_criteria_count: 3
  - id: 3
    name: Stub graph assembly
    depends_on: [1, 2]
    parallelizable: false
    automation: HITL
    automation_reason: "Establishes production workflow topology and routing."
    checkpoint_criteria_count: 3
  - id: 4
    name: HITL interrupt/resume service
    depends_on: [3]
    parallelizable: false
    automation: HITL
    automation_reason: "Human-gate semantics and resume safety require review."
    checkpoint_criteria_count: 3
  - id: 5
    name: Mutation handoff boundary
    depends_on: [4]
    parallelizable: false
    automation: HITL
    automation_reason: "Protects authoritative graph mutation boundary."
    checkpoint_criteria_count: 3
  - id: 6
    name: Replay/recovery integration
    depends_on: [3, 4, 5]
    parallelizable: false
    automation: HITL
    automation_reason: "Coordinates idempotency, replay, and checkpoint recovery."
    checkpoint_criteria_count: 3
```

> **Note:** `parallelizable` is a static planning-time hint, not a runtime guarantee. `crispy-implement` re-evaluates parallelizability dynamically based on dependency satisfaction and file-set conflict detection at execution time.

## Context Management
- Maximum files open per slice: 6 implementation files plus directly relevant tests.
- Recommended context window reset points: after Slice 1 and after Slice 4.
- State that must carry across slices: node seam contracts, deterministic `thread_id` rule, no-direct-write mutation rule, and WAL ownership constraints.

## Verification Strategy
Run unit and integration tests for workflow state, graph assembly, SQLite checkpoint restart, interrupt/resume commands, mutation-boundary enforcement, and replay/recovery. The full feature is verified when stub graph execution reaches HITL, persists checkpoint state, resumes deterministically, and routes approved mutation through `ApprovalBoundMutationService` only.
