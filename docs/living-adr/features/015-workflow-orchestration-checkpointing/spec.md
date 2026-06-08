# Feature Specification: workflow-orchestration-checkpointing

## Overview
Feature 015 assembles the production LangGraph workflow backbone for LivingADR. It wires normalized `SCMEvent` intake from feature 003 through stub classifier, draft, HITL, and approved-mutation nodes while production implementations arrive in features 008, 009, and 010. It owns durable in-flight workflow state through a SQLite-backed LangGraph checkpointer, including interrupt/resume and replay/recovery behavior required by `..\..\architecture.md#tech-stack`, `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`, and `..\..\architecture.md#cross-cutting`.

This feature deliberately does **not** implement production classification quality, Claude drafting, review UI, approval/audit durability, graph adapter behavior, or ADR publication. It defines the node seams those features plug into.

## User Stories

### [US-1] Assemble the durable workflow graph — Priority: P1
**As a** workflow-service maintainer, **I want** a production LangGraph graph assembled from typed node seams, **so that** downstream classifier, drafter, HITL, and mutation implementations can plug into one durable orchestration path.

#### Acceptance Scenarios
- **Given** a normalized merged-PR `SCMEvent` from feature 003, **When** the workflow is invoked, **Then** the graph executes intake, classification, draft, HITL gate, and mutation-handoff nodes in the configured order.
- **Given** real node implementations are unavailable, **When** the graph is built with stubs, **Then** the graph still produces deterministic state transitions suitable for tests and replay.

### [US-2] Persist in-flight workflow state — Priority: P1
**As a** platform operator, **I want** LangGraph checkpoints persisted to SQLite WAL storage, **so that** workflow state survives service restarts and can be recovered without an external queue.

#### Acceptance Scenarios
- **Given** a workflow reaches any configured checkpoint, **When** the process restarts, **Then** the same `thread_id` can load the persisted state.
- **Given** the workflow-service is the sole writer, **When** SQLite persistence is initialized, **Then** WAL mode and a short busy timeout are configured without granting write access to MCP or graph readers.

### [US-3] Interrupt for HITL and resume safely — Priority: P1
**As a** tech lead / approver, **I want** the workflow to interrupt before authoritative mutation and resume only from an explicit review command, **so that** graph mutation remains human-gated.

#### Acceptance Scenarios
- **Given** a draft reaches the HITL gate, **When** the gate node runs, **Then** LangGraph interrupts with a typed review payload and persists the pending checkpoint.
- **Given** a reviewer resume command is supplied, **When** the workflow resumes with the same `thread_id`, **Then** the state records approve/edit/reject intent and routes to mutation handoff only for approved decisions.

### [US-4] Support replay and recovery from intake failures — Priority: P1
**As a** platform operator, **I want** replay/recovery hooks that bridge feature 003 ingestion records into the graph, **so that** FM-01 missed ADRs and FM-17 webhook gaps/duplicates are testable and recoverable.

#### Acceptance Scenarios
- **Given** a stored delivery/event id from feature 003, **When** replay is requested, **Then** the workflow starts or resumes with deterministic `thread_id` derivation and idempotency metadata.
- **Given** a failed graph node, **When** the event is replayed, **Then** the checkpointer and ingestion idempotency prevent duplicate downstream side effects.

### [US-5] Preserve graph mutation and audit boundaries — Priority: P1
**As an** architecture owner, **I want** orchestration to call only the approval-bound mutation seam, **so that** this feature does not overlap with feature 010 approval/audit durability or bypass feature 006 mutation safety.

#### Acceptance Scenarios
- **Given** a resumed state lacks an approved capability, **When** the mutation handoff node runs, **Then** no `ArchitectureGraphStore` write method is called.
- **Given** an `ApprovedReviewDecision` capability is present, **When** mutation handoff runs, **Then** the graph calls `ApprovalBoundMutationService` and never calls graph adapter writes directly.

## Functional Requirements
- [FR-1] Define a `WorkflowState` model containing repository scope, `SCMEvent` reference, evidence references, classification output, draft reference/content hash, HITL interrupt payload, resume command, approved decision capability, mutation result, error metadata, and replay metadata.
- [FR-2] Define node protocols for intake, classifier, draft, HITL gate, and mutation handoff with explicit inputs/outputs.
- [FR-3] Provide deterministic stub node implementations for classifier, draft, and HITL/mutation seams so the graph is executable before features 008/009/010 land.
- [FR-4] Build the LangGraph state machine: intake → classify → draft → HITL interrupt → resume routing → mutation handoff / rejection terminal.
- [FR-5] Configure a SQLite-backed LangGraph checkpointer under workflow-service-owned state storage with WAL mode, busy timeout, startup setup, and test isolation.
- [FR-6] Require deterministic `thread_id` derivation from repository identity + normalized event key, while allowing explicit override for tests/operators.
- [FR-7] Expose a replay/resume service API callable by workflow-service handlers and operator tests; this is not a public UI.
- [FR-8] Ensure all graph write attempts flow through `ApprovalBoundMutationService` from feature 006.
- [FR-9] Emit only metadata-safe observability hooks using the feature 002 `Observability` seam; do not export raw diffs, prompts, drafts, or reviewer comments by default.

## Node-Seam Interfaces

### Intake seam from Feature 003
- **Producer:** `workflow.ingestion` / replay service from feature 003.
- **Input:** `SCMEvent` with `repository`, `provider_delivery_id`, `normalized_event_key`, PR refs, merge SHA, and evidence/fetch handles.
- **Output into graph:** `WorkflowState(event=..., evidence_refs=..., replay=...)`.
- **Contract:** no raw GitHub payloads enter graph nodes; provider-specific data remains behind `SCMProvider` or opaque evidence handles.

### Classifier node seam implemented by Feature 008
- **Protocol:** `StructuralClassifierNode.__call__(state: WorkflowState) -> WorkflowState`.
- **Inputs:** repository, normalized event, evidence references, configured structural-change thresholds.
- **Outputs:** `classification_result` containing zero or more `StructuralChange` values plus confidence and evidence ids, or `no_adr_needed` with reason.
- **Stub behavior:** deterministic dependency-like `StructuralChange` for configured tests, and explicit no-op variant for no-ADR paths.

### Draft node seam implemented by Feature 008
- **Protocol:** `ADRDraftNode.__call__(state: WorkflowState) -> WorkflowState`.
- **Inputs:** one selected `StructuralChange`, `ChangeEvidence`, repository config, and optional graph context query.
- **Outputs:** provisional `ADRDraft` reference/content, `adr_draft_content_hash`, evidence citation ids, and provisional-rationale flag.
- **Stub behavior:** simple Markdown draft with stable hash and no external LLM call.

### HITL interrupt/resume seam implemented by Feature 009 UI and Feature 010 decision durability
- **Protocol:** `HITLGateNode.__call__(state: WorkflowState) -> Interrupt[ReviewRequestPayload]` and resume with `ReviewResumeCommand`.
- **Interrupt payload:** repository, event key, draft id/hash, draft preview/ref, evidence ids, confidence, and allowed actions: approve, approve_after_edit, reject, defer.
- **Resume command:** action, optional edited draft content/hash, reviewer id, and optional `ApprovedReviewDecision` capability minted by feature 010.
- **Stub behavior:** raises/returns LangGraph interrupt payload and accepts synthetic resume commands in tests; it does not render UI or persist audit records.

### Mutation handoff seam from Feature 006 / completed by Feature 010
- **Protocol:** `MutationHandoffNode.__call__(state: WorkflowState) -> WorkflowState`.
- **Inputs:** approved decision capability, draft/ADR record reference, structural change, and mutation request.
- **Outputs:** mutation result or terminal rejection/defer result.
- **Contract:** call `ApprovalBoundMutationService`; never call `ArchitectureGraphStore` directly. Capability minting, one-shot consumption, TTL, audit durability, and decision lifecycle are owned by feature 010.

## Non-Functional Requirements
- [NFR-1] Durability: persisted checkpoints must survive process restart in local PoC storage.
- [NFR-2] Idempotency: event replay must not create duplicate graph mutations or duplicate review requests for the same repository/event/thread.
- [NFR-3] Security: untrusted SCM data and model output remain inert workflow state until HITL approval and approval-bound mutation validation.
- [NFR-4] Privacy: observability must follow default-deny raw export from `..\..\architecture.md#cross-cutting`.
- [NFR-5] Portability: implementation must keep SQLite-specific code behind a checkpointer factory so post-PoC migration is localized.
- [NFR-6] Testability: all node seams must be executable with fakes/stubs and no live GitHub, Claude, LangSmith, UI browser, or graph database.

## Out of Scope
- Production classifier algorithms and draft quality (feature 008 plugs real classifier/draft behavior into these seams).
- Claude client, prompt packaging, token budgeting, or production ADR quality (feature 008).
- Server-rendered review pages, forms, accessibility copy, or reviewer UX (feature 009).
- ApprovalEvent persistence, capability minting, TTL/one-shot consumption durability, and audit log completeness (feature 010).
- LlamaIndex graph adapter implementation and graph schema conformance (feature 007).
- GitHub ADR publication (feature 011), MCP query serving (feature 012), and LangSmith-backed observability dashboards (feature 013).

## Success Criteria
- [ ] Graph compiles with stub nodes and executes intake through HITL interrupt in tests.
- [ ] SQLite-backed checkpointer persists pending HITL state and reloads it after simulated restart.
- [ ] Resume with approve/reject/defer commands routes deterministically and preserves state history.
- [ ] Replay of a stored normalized event uses deterministic thread identity and avoids duplicate side effects.
- [ ] Mutation handoff uses `ApprovalBoundMutationService` only.
- [ ] Node seam documentation is sufficient for features 008, 009, and 010 to implement real nodes without changing graph assembly.

## Open Questions
- Which exact LangGraph SQLite checkpointer package import path is available under the pinned dependency set must be verified during implementation; add `langgraph-checkpoint-sqlite` only if LangGraph 1.2.1 does not include the SQLite saver.
- The final production review command schema may gain fields from features 009/010; this feature should keep the seam versioned and backwards-compatible.
