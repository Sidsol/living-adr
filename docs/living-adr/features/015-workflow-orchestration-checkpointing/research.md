# Research: workflow-orchestration-checkpointing

> Feature-level research for LivingADR feature 015. Sources include project planning docs plus public LangGraph checkpoint/interrupt documentation. This is a greenfield feature: no production `living-adr` code is assumed beyond dependency contracts from features 003 and 006.

## Architecture Overview
LivingADR architecture selects a hybrid single repository with two deployables. The `workflow-service` owns SCM webhook receipt, LangGraph orchestration, Claude calls, HITL review state/UI, audit log, and approved publication workflow, while `mcp-context-server` is read-only and isolated (`..\..\architecture.md#service-boundaries`).

The relevant orchestration role split is explicit in `..\..\architecture.md#tech-stack`: LangGraph owns workflow/state-machine orchestration from webhook intake to classification, ADR draft generation, HITL gate, and graph mutation. LlamaIndex is only a graph/retrieval implementation behind ports and must not orchestrate workflow.

## Source Inputs Read
- `..\..\architecture.md`: tech stack, service boundaries, data model, cross-cutting, deployment, anti-patterns.
- `..\..\domain-research.md`: FM-01 ADR not created at decision time, FM-17 SCM duplication/gaps/replay, LangGraph/HITL glossary.
- `..\..\vision.md`: TH-03 human review workflow, SM-02 latency, SM-05 no unapproved mutations.
- `..\..\feature-map.md`: feature 015 brief and dependencies on 003 and 006.
- `..\..\roadmap.md`: M3 exit criterion requires LangGraph workflow durably checkpoints intake through HITL interrupt/resume seams.
- `..\003-github-webhook-ingestion\intent.md`: normalized `SCMEvent`, candidate evidence, replay/dead-letter, and instruction not to build checkpointing in 003.
- `..\006-graph-store-ports-and-approval-seam\intent.md`: `ApprovalBoundMutationService`, graph ports, approval capability boundary, and limitation that feature 010 owns durable approval semantics.

## LangGraph Findings
- LangGraph is designed for long-running, stateful workflows with durable execution, interrupts/HITL, and persistence. It is a better fit than ad hoc function chains for this feature because graph state, node routing, and checkpoints are first-class.
- Workflows are compiled from typed state and node functions. A production graph can be assembled with stub node callables as long as each seam obeys stable state input/output contracts.
- Human-in-the-loop flows are modeled by interrupting graph execution with a payload, persisting the checkpoint, and resuming with a command on the same configured thread.
- LangGraph checkpoint identity is driven by runtime configuration. The feature should standardize `thread_id` as repository identity + normalized event key and reserve `checkpoint_id` for LangGraph-managed history or explicit recovery.

## SQLite Checkpointer Findings
- A SQLite checkpointer fits the PoC architecture because the workflow-service is a single writer and both deployables share a local filesystem (`..\..\architecture.md#deployment`).
- SQLite must run in WAL mode with a short busy timeout to match the architecture's concurrent persistence rule. The workflow-service owns write connections; MCP and graph read paths must remain read-only.
- The checkpointer stores LangGraph in-flight workflow state; it is distinct from:
  - feature 003 ingestion delivery/evidence replay tables,
  - feature 010 approval/audit durability,
  - feature 007 graph projection persistence.
- Implementation should hide checkpointer creation behind `workflow.checkpointing` so a future Postgres or server-based store does not reshape graph nodes.

## Interrupt/Resume Findings
- HITL should interrupt after an ADR draft is available and before any authoritative mutation. The interrupt payload must be reviewable but should avoid raw sensitive blobs in observability.
- Resume must supply a typed command: approve, approve-after-edit, reject, or defer. Approve commands may carry an `ApprovedReviewDecision` capability once feature 010 exists.
- Reject/defer are terminal or waiting states that must not call mutation services.
- Resuming by event key without stable thread configuration risks starting a duplicate workflow. The resume service must require or derive the same `thread_id` used at intake.

## Dependency Contracts Observed

### Feature 003 — GitHub webhook ingestion
Feature 003 intends to expose:
- `SCMEvent`: repository-scoped normalized merged-PR event with provider delivery id and normalized event key.
- `SCMProvider`: provider-neutral fetch port.
- `CandidateEvidence`: immutable evidence linked to event and changed files/diff handles.
- `ReplayService`: reprocesses stored delivery/event records while preserving idempotency.

Feature 015 should consume these contracts and not parse raw GitHub payloads.

### Feature 006 — graph store ports and approval seam
Feature 006 intends to expose:
- `ArchitectureGraphStore` write-side port.
- `ArchitectureContextQuery` read-side port.
- `ADRRecordRepository` expectations.
- `ApprovedReviewDecision` capability object.
- `ApprovalBoundMutationService` as the only allowed graph mutation path.

Feature 015 should call only `ApprovalBoundMutationService` from mutation handoff nodes and must not implement capability minting, audit linkage, TTL, or one-shot consumption durability.

## Logic Flows to Preserve

### Flow: New normalized event to pending review
1. Feature 003 receives/replays a merged PR and creates `SCMEvent` + evidence.
2. Workflow-service derives `thread_id` from repository + normalized event key.
3. LangGraph starts with intake state and checkpoint config.
4. Classifier node produces `StructuralChange` or `no_adr_needed`.
5. Draft node produces provisional `ADRDraft` and hash.
6. HITL gate interrupts with review payload and persists pending state.

### Flow: Reviewer resume to mutation handoff
1. Review UI or test harness posts `ReviewResumeCommand` for the same thread.
2. LangGraph reloads pending checkpoint and applies resume command.
3. Router sends reject/defer to terminal/waiting state.
4. Router sends approved decisions to mutation handoff.
5. Mutation handoff calls `ApprovalBoundMutationService` only if a valid capability is present.
6. Checkpoint records result and terminal state.

### Flow: Replay/recovery
1. Operator/test selects stored event/delivery id from feature 003.
2. Replay service reconstructs normalized event/evidence references.
3. Workflow start/resume uses deterministic thread id.
4. Checkpointer restores prior state if present; otherwise starts from intake.
5. Idempotency metadata prevents duplicate review/mutation side effects.

## Data Model Notes
- `RepositoryIdentity`, `SCMEvent`, `StructuralChange`, `ChangeEvidence`, `ADRDraft`, `ApprovedReviewDecision`, `ADRRecord`, and `AuditEvent` are architecture-level concepts (`..\..\architecture.md#data-model`).
- Feature 015 adds no new authoritative domain record. It adds workflow state envelopes, interrupt payloads, resume commands, and checkpoint metadata.
- Workflow state should store references or hashes for large/sensitive content where possible; raw diffs and full prompts should not be emitted to observability.

## Integration Points

| Integration | Type | Owner | Notes |
|---|---|---|---|
| Feature 003 ingestion | Internal port | `workflow.ingestion` / replay | Supplies `SCMEvent` and evidence references. |
| LangGraph | Runtime | feature 015 | Owns graph assembly, routing, interrupts, and checkpoints. |
| SQLite checkpointer | Local persistence | feature 015 | In-flight workflow state only; WAL and workflow-service write ownership. |
| Feature 008 classifier/draft | Node plugin seam | downstream producer | Implements real classifier/draft protocols without changing graph assembly. |
| Feature 008 drafting | Node plugin seam | draft feature | Implements ADR draft node and Claude behavior. |
| Feature 009 HITL UI | Resume caller / payload renderer | UI feature | Renders interrupt payload and submits resume command. |
| Feature 010 approval/audit | Capability and durability | approval feature | Mints durable decisions and records audit; feature 015 only consumes capability. |
| Feature 006 mutation service | Internal service | graph seam feature | Only graph write path from mutation handoff. |

## Configuration & Environment
- Checkpoint database path should come from existing settings/config conventions and default under `var\workflow\` or equivalent workflow-service state path.
- WAL setup should be explicit at startup (`journal_mode=WAL`, busy timeout).
- Test paths should be isolated per test and not use production state.
- No secrets are required by this feature beyond dependencies already used by ingestion/drafting in other features.

## Technical Debt & Observations
- The architecture pins `langgraph==1.2.1` but does not separately list a SQLite checkpoint package. Implementation must verify whether SQLite saver is bundled or requires `langgraph-checkpoint-sqlite`.
- Feature 010 owns approval/audit durability, so feature 015 tests must avoid asserting final durable audit behavior. They should assert routing and service invocation boundaries only.
- Feature 009 owns UI accessibility and review ergonomics; feature 015 should keep interrupt payload typed and renderable but not embed HTML concerns.
- Feature 003 already has replay/dead-letter state. Feature 015 should reuse event replay inputs rather than creating a second ingestion inbox.

## Key Patterns
- Typed ports in `core`; concrete runtime glue under `workflow` and `apps\workflow_service`.
- Repository scope on every workflow state and node input.
- Deterministic, fake-friendly tests for LLM-bearing and HITL-bearing nodes.
- Default-deny observability export for raw diffs, prompts, drafts, and reviewer comments.
- Single writer with SQLite WAL for PoC durability.
