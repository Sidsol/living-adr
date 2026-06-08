# Architecture Intent: workflow-orchestration-checkpointing

## Current State
LivingADR is a greenfield project whose architecture already assigns workflow/state-machine orchestration to LangGraph and local durable state to SQLite (`..\..\architecture.md#tech-stack`). Feature 003 plans the normalized `SCMEvent`, evidence, idempotency, replay, and dead-letter contract. Feature 006 plans graph/read ports and `ApprovalBoundMutationService`, the only safe mutation path.

No production orchestration backbone exists yet for intake → classify → draft → HITL interrupt/resume → mutation handoff. Without this feature, downstream features 008/009/010 have no stable graph seam to plug into and replay/recovery remains split across ingestion state without in-flight workflow checkpointing.

## Desired State
After implementation, `workflow-service` has a production LangGraph graph compiled from typed node seams. The graph can run with deterministic stub classifier, draft, HITL, and mutation-handoff nodes while production classifier/draft/UI/approval features plug in later. A SQLite-backed checkpointer persists in-flight state, supports HITL interrupt/resume, and allows replay/recovery using deterministic thread identity.

The selected design references:
- `..\..\architecture.md#tech-stack`: LangGraph owns orchestration; checkpointer holds in-flight state.
- `..\..\architecture.md#service-boundaries`: workflow-service is the sole writer; graph mutation goes through approval-bound seam.
- `..\..\architecture.md#data-model`: state carries `RepositoryIdentity`, `SCMEvent`, `StructuralChange`, `ADRDraft`, and `ApprovedReviewDecision` references.
- `..\..\architecture.md#cross-cutting`: idempotency, replayable failures, default-deny observability, single-writer WAL.
- `..\..\architecture.md#anti-patterns`: FM-01 and FM-17 require ADR creation at decision time and replay/recovery.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Graph assembly | Architecture brief only | LangGraph state machine compiled in workflow package | Create graph builder, routing, and app wiring |
| Workflow state | Domain models planned separately | Typed `WorkflowState`, interrupt payloads, resume commands | Define orchestration state models without owning external domain records |
| Node seams | Downstream features know broad responsibilities | Protocols for classifier, draft, HITL, mutation handoff | Document and test explicit seams for 008/009/010 |
| Stub execution | Walking skeleton may have ad hoc stubs | Production graph runs with deterministic stubs | Add stub node implementations and tests |
| Checkpointing | SQLite chosen but not wired to LangGraph | Checkpointer factory, WAL setup, startup validation | Implement `workflow.checkpointing` with isolated tests |
| HITL interrupt/resume | Required by architecture | Pending review checkpoint and typed resume command | Add interrupt node/router and resume service |
| Replay/recovery | Feature 003 ingestion replay only | Replay bridges stored normalized events into deterministic graph threads | Add orchestration replay entrypoint and tests |
| Mutation safety | Feature 006 provides service | Graph calls `ApprovalBoundMutationService` only | Add handoff node and no-direct-write tests |

## Architecture Options

### Option A: Ad hoc async function pipeline
**Approach:** Implement intake/classify/draft/review/mutate as Python functions called sequentially, with manual SQLite state records.
- ✅ Pros: Lower dependency learning curve; easy to debug initially.
- ❌ Cons: Violates LangGraph ownership from `..\..\architecture.md#tech-stack`; duplicates checkpoint/resume semantics; harder for 008/009/010 to plug in safely.
- 🔧 Effort: Low now, high later.

### Option B: LangGraph graph with in-memory checkpointer until UI is ready
**Approach:** Assemble graph now, but use only in-memory checkpoints and postpone SQLite/HITL durability to feature 009 or 010.
- ✅ Pros: Faster graph assembly and unit tests.
- ❌ Cons: Fails FM-01/FM-17 recovery goals; makes HITL interrupt non-durable; pushes orchestration durability into UI/audit features where it does not belong.
- 🔧 Effort: Medium.

### Option C: LangGraph graph with SQLite checkpointer and typed stub-node seams (selected)
**Approach:** Compile the production graph now, persist in-flight state with SQLite WAL, interrupt at the HITL seam, resume with typed commands, and use deterministic stubs until real nodes land.
- ✅ Pros: Aligns with all architecture anchors; gives downstream features executable seams; makes replay/recovery testable; keeps approval/audit and UI boundaries separate.
- ❌ Cons: Requires careful dependency and package validation for SQLite saver; more interface design before production node quality exists.
- 🔧 Effort: Medium-to-High.

## Selected Approach
**Option C: LangGraph graph with SQLite checkpointer and typed stub-node seams.**

Rationale: Feature 015 is high-leverage because it stabilizes the orchestration backbone before 008/009/010. The graph and checkpointer must be production-shaped now so later features implement nodes rather than each inventing workflow control. SQLite checkpointing belongs here, while approval/audit durability stays in 010 and UI stays in 009.

## Module Surface Analysis

| Module | Inputs | Callers | Deletion test | Isolated-test candidate |
|---|---:|---|---|---|
| `src\living_adr\workflow\state.py` | domain refs, command values, timestamps | all workflow nodes/tests | Deleting forces untyped dict state | Yes — pure model tests |
| `src\living_adr\workflow\nodes\protocols.py` | `WorkflowState` | graph builder, downstream features | Deleting removes plug-in seam for 008/009/010 | Yes — import/signature tests |
| `src\living_adr\workflow\nodes\stubs.py` | state + deterministic config | tests, local graph factory | Deleting prevents graph execution before real nodes | Yes — pure deterministic tests |
| `src\living_adr\workflow\graph.py` | node implementations, checkpointer | workflow app, replay/resume services | Deleting removes orchestration backbone | Yes with fake checkpointer/nodes |
| `src\living_adr\workflow\checkpointing.py` | database path/settings | app startup, graph factory | Deleting removes durable state | Partially — SQLite integration tests |
| `src\living_adr\workflow\review_resume.py` | thread id, resume command, graph | HITL UI feature, tests | Deleting prevents HITL resume | Yes with compiled stub graph |
| `src\living_adr\workflow\replay.py` | stored event id / SCMEvent, graph | operator endpoint/CLI/tests | Deleting weakens FM-17 recovery | Yes with fake ingestion source |
| `src\living_adr\apps\workflow_service\workflow_routes.py` | app deps, request models | FastAPI app | Deleting leaves no local resume/replay hook | Partially — ASGI tests |
| `tests\workflow\test_graph_stub_flow.py` | stubs, fake event | pytest | Deleting risks broken graph order | n/a |
| `tests\workflow\test_checkpoint_resume.py` | SQLite db, compiled graph | pytest | Deleting risks non-durable HITL | n/a |
| `tests\workflow\test_replay_recovery.py` | fake ingestion source | pytest | Deleting risks FM-17 regression | n/a |
| `tests\workflow\test_mutation_boundary.py` | fake mutation service/store | pytest | Deleting risks direct graph writes | n/a |

## Stub-Node Seam Definitions
- **Classifier seam:** `StructuralClassifierNode` consumes `WorkflowState` and returns state with `classification_result`. Feature 008 implements the real classifier/draft behavior behind this seam.
- **Draft seam:** `ADRDraftNode` consumes classified state and returns state with draft reference/content hash. Feature 008 implements Claude drafting.
- **HITL seam:** `HITLGateNode` interrupts with `ReviewRequestPayload` and resumes with `ReviewResumeCommand`. Feature 009 renders the payload; feature 010 may attach durable approval capabilities.
- **Mutation seam:** `MutationHandoffNode` consumes approved state and calls `ApprovalBoundMutationService`. Feature 010 completes durable approval/audit semantics; this feature only routes.

## Anti-Patterns to Avoid
- **UI-owned orchestration:** feature 009 must render and resume; it must not own graph topology or checkpointing.
- **Audit-owned checkpointing:** feature 010 owns approval/audit durability, not LangGraph in-flight state.
- **Direct graph adapter writes:** mutation handoff must not call `ArchitectureGraphStore` directly.
- **Raw GitHub payload in graph state:** violates feature 003 provider-neutral contract and FM-24.
- **In-memory-only HITL:** loses pending review state on restart and violates FM-01/FM-17 mitigation.
- **Second ingestion inbox:** reuse feature 003 event/replay contracts; do not duplicate webhook delivery storage.
- **LlamaIndex workflow orchestration:** LlamaIndex stays behind graph/query ports and is invoked from nodes only.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add workflow state, graph assembly, checkpointing, stubs, resume/replay services, workflow-service hooks, and tests | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LangGraph SQLite saver package/import mismatch | Medium | Medium | Validate dependency in first slice; isolate import in `checkpointing.py`; add package only if required. |
| Stub seams drift from production node needs | Medium | High | Document protocols; add contract tests; include 008/009/010 payload fields without implementing their internals. |
| Checkpoint DB conflicts with ingestion/audit stores | Medium | Medium | Keep separate path/table namespace; document ownership; no audit tables here. |
| Resume starts duplicate thread | Medium | High | Deterministic thread id from repository + normalized event key; tests for restart/resume. |
| Replays duplicate mutations | Medium | High | Require idempotency metadata and approval-bound service; test no call without capability. |
| Raw sensitive content leaks to observability | Medium | High | Metadata-only event names and ids; no raw diffs/drafts/comments in traces. |
| Single-writer/WAL violated by convenience readers | Low | High | Checkpointer factory opens workflow writer only; document read-only constraints for other processes. |
