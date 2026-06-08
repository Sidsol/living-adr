# Implementation Plan: workflow-orchestration-checkpointing

## Technical Context
- Language/Framework: Python 3.12, FastAPI workflow-service, LangGraph 1.2.1.
- Key Dependencies: `langgraph`, stdlib `sqlite3`, project core contracts from features 003/006; validate whether `langgraph-checkpoint-sqlite` is required.
- Test Framework: pytest.
- Build System: uv workspace with Ruff.

## Project Structure

```text
src\living_adr\
├── apps\workflow_service\
│   └── workflow_routes.py              ← CREATE/MODIFY: internal start/resume/replay hooks
├── workflow\
│   ├── __init__.py                      ← MODIFY: export graph/checkpoint services as needed
│   ├── state.py                         ← CREATE: workflow state and review/replay models
│   ├── checkpointing.py                 ← CREATE: SQLite checkpointer factory and WAL setup
│   ├── graph.py                         ← CREATE: LangGraph assembly and routing
│   ├── review_resume.py                 ← CREATE: start/resume API for HITL commands
│   ├── replay.py                        ← CREATE: orchestration replay bridge
│   └── nodes\
│       ├── __init__.py                  ← CREATE
│       ├── protocols.py                 ← CREATE: node Protocol definitions
│       └── stubs.py                     ← CREATE: deterministic stub nodes
└── core\                               ← READ/USE: SCMEvent, graph/approval ports from deps

tests\workflow\
├── test_workflow_state.py               ← CREATE
├── test_node_protocols.py               ← CREATE
├── test_checkpointing.py                ← CREATE
├── test_graph_stub_flow.py              ← CREATE
├── test_review_resume.py                ← CREATE
├── test_mutation_boundary.py            ← CREATE
└── test_replay_recovery.py              ← CREATE
```

## Implementation Phases

### Phase 1: State and node seam contracts

#### Step 1.1: Define workflow state models
- **File:** `src\living_adr\workflow\state.py`
- **Action:** Create
- **Changes:** Add `WorkflowState`, `WorkflowStatus`, `ReviewRequestPayload`, `ReviewResumeCommand`, `WorkflowReplayMetadata`, and lightweight error/result models. Store domain object references/hashes rather than raw provider payloads.

#### Step 1.2: Test workflow state validation
- **File:** `tests\workflow\test_workflow_state.py`
- **Action:** Create
- **Changes:** RED→GREEN tests for repository/event required fields, deterministic thread key inputs, review command actions, and sensitive raw payload exclusion.

#### Step 1.3: Define node protocols
- **File:** `src\living_adr\workflow\nodes\protocols.py`
- **Action:** Create
- **Changes:** Add `IntakeNode`, `StructuralClassifierNode`, `ADRDraftNode`, `HITLGateNode`, and `MutationHandoffNode` Protocols with `WorkflowState` input/output docstrings for 008/009/010.

#### Step 1.4: Add deterministic stub nodes
- **File:** `src\living_adr\workflow\nodes\stubs.py`
- **Action:** Create
- **Changes:** Add configurable stubs for classify, draft, HITL interrupt payload, and mutation handoff. Stubs must not call Claude, UI, GitHub, or concrete graph adapters.

#### Step 1.5: Test protocol/stub behavior
- **File:** `tests\workflow\test_node_protocols.py`
- **Action:** Create
- **Changes:** Tests assert stubs satisfy protocols and produce stable classification/draft/review payloads.

### Phase 2: SQLite checkpointer factory

#### Step 2.1: Validate LangGraph SQLite dependency
- **File:** `pyproject.toml`
- **Action:** Modify if required
- **Changes:** If implementation proves SQLite saver is not available from pinned `langgraph`, add the official SQLite checkpointer package with a pinned compatible version; otherwise make no dependency change.

#### Step 2.2: Implement checkpointer factory
- **File:** `src\living_adr\workflow\checkpointing.py`
- **Action:** Create
- **Changes:** Add `WorkflowCheckpointConfig`, SQLite connection setup, WAL mode, busy timeout, schema/setup call, and checkpointer creation behind a single function.

#### Step 2.3: Test checkpoint setup and persistence
- **File:** `tests\workflow\test_checkpointing.py`
- **Action:** Create
- **Changes:** Tests verify WAL mode, busy timeout, path creation, and state persistence across separate checkpointer instances.

### Phase 3: Stub graph assembly

#### Step 3.1: Build LangGraph graph
- **File:** `src\living_adr\workflow\graph.py`
- **Action:** Create
- **Changes:** Add graph builder that injects node implementations, defines edges intake → classify → draft → HITL → resume router → mutation/reject/defer terminal, and compiles with the supplied checkpointer.

#### Step 3.2: Export workflow graph API
- **File:** `src\living_adr\workflow\__init__.py`
- **Action:** Modify
- **Changes:** Export graph builder, state models, and checkpointer factory without importing concrete app/web dependencies.

#### Step 3.3: Test stub graph execution
- **File:** `tests\workflow\test_graph_stub_flow.py`
- **Action:** Create
- **Changes:** Tests start a fake normalized event, assert node order, HITL interrupt payload, persisted status, and no-ADR terminal path.

### Phase 4: HITL interrupt/resume service

#### Step 4.1: Implement review resume service
- **File:** `src\living_adr\workflow\review_resume.py`
- **Action:** Create
- **Changes:** Add `start_workflow_for_event`, `resume_review`, deterministic `thread_id` derivation, resume config construction, and typed result mapping.

#### Step 4.2: Add workflow-service hook seam
- **File:** `src\living_adr\apps\workflow_service\workflow_routes.py`
- **Action:** Create/Modify
- **Changes:** Add internal handler/route functions for start/resume/replay integration used by feature 009 later; keep UI rendering out of scope.

#### Step 4.3: Test resume commands
- **File:** `tests\workflow\test_review_resume.py`
- **Action:** Create
- **Changes:** Tests for approve, approve-after-edit, reject, defer, wrong thread id, and restart-before-resume behavior.

### Phase 5: Mutation handoff boundary

#### Step 5.1: Implement mutation handoff behavior
- **File:** `src\living_adr\workflow\nodes\stubs.py`
- **Action:** Modify
- **Changes:** Ensure handoff node calls `ApprovalBoundMutationService` only when state includes approved action and capability; otherwise returns terminal no-mutation status.

#### Step 5.2: Test mutation boundary
- **File:** `tests\workflow\test_mutation_boundary.py`
- **Action:** Create
- **Changes:** Tests assert no call without capability/rejected/deferred states, exactly one service call for approved state, and no direct graph adapter import/write.

### Phase 6: Replay/recovery integration

#### Step 6.1: Implement replay bridge
- **File:** `src\living_adr\workflow\replay.py`
- **Action:** Create
- **Changes:** Add service that accepts stored event id or normalized `SCMEvent`, obtains evidence references from feature 003 seam, derives thread id, starts/resumes graph, and records replay metadata in state.

#### Step 6.2: Wire replay hook into app seam
- **File:** `src\living_adr\apps\workflow_service\workflow_routes.py`
- **Action:** Modify
- **Changes:** Add operator/test callable replay handler; no public UI commitment.

#### Step 6.3: Test replay/recovery
- **File:** `tests\workflow\test_replay_recovery.py`
- **Action:** Create
- **Changes:** Tests replay same event twice, recover from pending HITL checkpoint, and ensure duplicate replay does not duplicate mutation/review side effects.

## Complexity Tracking

| Phase | Files Changed | New Files | Estimated Effort | Risk |
|---|---:|---:|---|---|
| Phase 1 | 0 | 5 | M | Medium |
| Phase 2 | 0-1 | 2 | M | Medium |
| Phase 3 | 1 | 2 | M | Medium |
| Phase 4 | 1 | 2 | M | High |
| Phase 5 | 1 | 1 | M | High |
| Phase 6 | 1 | 1 | M | High |

## Dependencies & Prerequisites
- Feature 003 contracts: `SCMEvent`, evidence references, replay source/dead-letter state.
- Feature 006 contracts: `ApprovedReviewDecision`, `ApprovalBoundMutationService`, graph ports, ADR value objects.
- Existing settings/config convention from feature 002 for storage paths.
- Confirm LangGraph SQLite checkpointer package/import compatibility before Phase 2 GREEN.

## Rollback Strategy
- Phase 1 rollback: remove workflow state/seam modules and associated tests; no persistence side effects.
- Phase 2 rollback: remove checkpointer module and dependency addition if any; delete only test-created SQLite files.
- Phase 3 rollback: remove graph builder exports; stub modules remain harmless if retained.
- Phase 4 rollback: disable app seam handlers and keep graph tests for local invocation.
- Phase 5 rollback: revert mutation handoff node to no-op; no graph adapter writes should have occurred.
- Phase 6 rollback: disable replay hook; feature 003 replay remains intact.

## Machine-Readable Task Graph

```yaml
task_graph:
  - id: TASK-001
    slice: 1
    story: US-1
    depends_on: []
    parallelizable_with: []
    files: ["src\\living_adr\\workflow\\state.py"]
  - id: TASK-002
    slice: 1
    story: US-1
    depends_on: [TASK-001]
    parallelizable_with: []
    files: ["tests\\workflow\\test_workflow_state.py"]
  - id: TASK-003
    slice: 1
    story: US-1
    depends_on: [TASK-001]
    parallelizable_with: []
    files: ["src\\living_adr\\workflow\\nodes\\protocols.py"]
  - id: TASK-004
    slice: 1
    story: US-1
    depends_on: [TASK-003]
    parallelizable_with: []
    files: ["src\\living_adr\\workflow\\nodes\\stubs.py", "src\\living_adr\\workflow\\nodes\\__init__.py"]
  - id: TASK-005
    slice: 1
    story: US-1
    depends_on: [TASK-004]
    parallelizable_with: []
    files: ["tests\\workflow\\test_node_protocols.py"]
  - id: TASK-006
    slice: 2
    story: US-2
    depends_on: [TASK-005]
    parallelizable_with: []
    files: ["pyproject.toml"]
  - id: TASK-007
    slice: 2
    story: US-2
    depends_on: [TASK-006]
    parallelizable_with: []
    files: ["src\\living_adr\\workflow\\checkpointing.py"]
  - id: TASK-008
    slice: 2
    story: US-2
    depends_on: [TASK-007]
    parallelizable_with: []
    files: ["tests\\workflow\\test_checkpointing.py"]
  - id: TASK-009
    slice: 3
    story: US-1
    depends_on: [TASK-008]
    parallelizable_with: []
    files: ["src\\living_adr\\workflow\\graph.py"]
  - id: TASK-010
    slice: 3
    story: US-1
    depends_on: [TASK-009]
    parallelizable_with: []
    files: ["src\\living_adr\\workflow\\__init__.py"]
  - id: TASK-011
    slice: 3
    story: US-1
    depends_on: [TASK-010]
    parallelizable_with: []
    files: ["tests\\workflow\\test_graph_stub_flow.py"]
  - id: TASK-012
    slice: 4
    story: US-3
    depends_on: [TASK-011]
    parallelizable_with: []
    files: ["src\\living_adr\\workflow\\review_resume.py"]
  - id: TASK-013
    slice: 4
    story: US-3
    depends_on: [TASK-012]
    parallelizable_with: []
    files: ["src\\living_adr\\apps\\workflow_service\\workflow_routes.py"]
  - id: TASK-014
    slice: 4
    story: US-3
    depends_on: [TASK-013]
    parallelizable_with: []
    files: ["tests\\workflow\\test_review_resume.py"]
  - id: TASK-015
    slice: 5
    story: US-5
    depends_on: [TASK-014]
    parallelizable_with: []
    files: ["src\\living_adr\\workflow\\nodes\\stubs.py"]
  - id: TASK-016
    slice: 5
    story: US-5
    depends_on: [TASK-015]
    parallelizable_with: []
    files: ["tests\\workflow\\test_mutation_boundary.py"]
  - id: TASK-017
    slice: 6
    story: US-4
    depends_on: [TASK-016]
    parallelizable_with: []
    files: ["src\\living_adr\\workflow\\replay.py"]
  - id: TASK-018
    slice: 6
    story: US-4
    depends_on: [TASK-017]
    parallelizable_with: []
    files: ["src\\living_adr\\apps\\workflow_service\\workflow_routes.py"]
  - id: TASK-019
    slice: 6
    story: US-4
    depends_on: [TASK-018]
    parallelizable_with: []
    files: ["tests\\workflow\\test_replay_recovery.py"]
```
