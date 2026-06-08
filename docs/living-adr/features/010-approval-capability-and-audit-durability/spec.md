# Feature Specification: approval-capability-and-audit-durability

## Overview

Feature 010 turns feature 009's human review result into LivingADR's authoritative approval capability and durable audit trail. It consumes feature 015's `ReviewResumeCommand` and feature 009's approve / approve-after-edit / reject / defer UI decisions, persists immutable `ApprovalEvent` records, mints an `ApprovedReviewDecision` only for approved outcomes, enforces one-shot and TTL semantics, binds approval to the exact reviewed ADR content hash, and exposes `ApprovalBoundMutationService` as the sole path for downstream authoritative mutations.

This feature is the enforcement half of the HITL approval workflow. It depends on feature 009 for reviewer intent capture, feature 015 for workflow interrupt/resume checkpointing, and feature 007/006 for graph query/store ports. Its audit durability is an append-only business/audit record and is intentionally distinct from feature 015's LangGraph checkpointer durability for in-flight workflow state.

## User Stories

### [US-1] Persist review decisions durably — Priority: P1
**As an** architecture owner, **I want** every approve, approve-after-edit, reject, and defer decision recorded durably, **so that** LivingADR can prove which human decision led to each authoritative outcome.

#### Acceptance Scenarios
- **Given** feature 009 submits a `ReviewResumeCommand(action="approve")`, **When** feature 010 handles it, **Then** an append-only `ApprovalEvent` is stored with repository identity, reviewer id, draft id, reviewed content hash, workflow thread id, event key, timestamp, and outcome.
- **Given** a reviewer rejects or defers a draft, **When** the decision is recorded, **Then** no `ApprovedReviewDecision` is minted and the audit record captures the non-authorizing outcome and reason.

### [US-2] Mint an ApprovedReviewDecision capability — Priority: P1
**As a** workflow-service implementer, **I want** approved review outcomes to mint a typed capability object, **so that** downstream mutation code can distinguish human-authorized actions from provisional drafts.

#### Acceptance Scenarios
- **Given** an unchanged draft is approved, **When** minting succeeds, **Then** the capability references the original draft hash from features 008/009/015.
- **Given** a draft is approved after edit, **When** minting succeeds, **Then** the capability binds to the edited content hash and the edited rendered ADR content that the reviewer approved.
- **Given** action is reject or defer, **When** handling completes, **Then** no capability exists in the resume state.

### [US-3] Enforce TTL and expiry — Priority: P1
**As a** platform operator, **I want** approval capabilities to expire quickly, **so that** stale approvals cannot authorize later or tampered mutations.

#### Acceptance Scenarios
- **Given** a capability has `decision_minted_at` older than the configured TTL, **When** `ApprovalBoundMutationService` validates it, **Then** it raises `DecisionExpiredError` before any graph or publication mutation.
- **Given** no TTL override is configured, **When** a capability is minted, **Then** the PoC default TTL is 10 minutes.

### [US-4] Enforce one-shot and idempotent retry semantics — Priority: P1
**As an** audit owner, **I want** each approval capability consumed exactly once, **so that** a single human approval cannot authorize multiple authoritative mutations.

#### Acceptance Scenarios
- **Given** an unconsumed capability is used for its target mutation fingerprint, **When** mutation succeeds, **Then** consumption is recorded atomically with the mutation audit linkage.
- **Given** the same capability is retried with the same target mutation fingerprint after a successful commit, **When** the service handles the retry, **Then** it returns the prior result without performing a second mutation.
- **Given** the same capability is submitted for a different mutation fingerprint, **When** validation runs, **Then** it raises `DecisionAlreadyConsumedError`.

### [US-5] Bind approval to ADR content hash — Priority: P1
**As a** reviewer, **I want** my approval to bind to the exact ADR text I reviewed, **so that** post-approval tampering is detected before publication or graph mutation.

#### Acceptance Scenarios
- **Given** an approved draft's rendered content changes after approval, **When** `ApprovalBoundMutationService` recomputes the hash, **Then** it raises `DraftContentMismatchError` and records a failed validation audit event.
- **Given** approved content is unchanged, **When** validation runs, **Then** the hash matches `adr_draft_content_hash` and mutation may proceed subject to TTL and one-shot checks.

### [US-6] Route all authoritative mutations through ApprovalBoundMutationService — Priority: P1
**As an** architecture owner, **I want** one service to validate approvals before any write, **so that** graph writes and future publish-back cannot bypass HITL authority.

#### Acceptance Scenarios
- **Given** downstream feature 011 needs to publish an ADR, **When** it invokes the authorized path, **Then** it must supply an `ApprovedReviewDecision` and mutation fingerprint to `ApprovalBoundMutationService` or a feature-010-approved adapter around it.
- **Given** workflow or MCP code attempts direct `ArchitectureGraphStore` mutation, **When** boundary tests run, **Then** those paths fail or are absent.

### [US-7] Keep audit durability separate from workflow checkpointing — Priority: P1
**As a** maintainer, **I want** approval audit records independent from LangGraph checkpoints, **so that** recovery, compliance, and SM-05 checks do not depend on ephemeral workflow-state retention.

#### Acceptance Scenarios
- **Given** a workflow checkpoint is compacted, replayed, or replaced by feature 015, **When** approval audit records are queried, **Then** decision and consumption records remain intact.
- **Given** an audit store failure occurs while checkpointing succeeds, **When** approval handling runs, **Then** capability minting fails closed and no mutation is authorized.

## Functional Requirements

- [FR-1] Consume feature 015 `ReviewResumeCommand` values produced by feature 009 without changing the review UI contract.
- [FR-2] Persist immutable `ApprovalEvent` records for approve, approve-after-edit, reject, and defer outcomes.
- [FR-3] Mint `ApprovedReviewDecision` only for approve and approve-after-edit outcomes.
- [FR-4] Include repository, reviewer, draft, structural-change event, workflow thread, decision version, target mutation fingerprint, content hash, mint timestamp, TTL, and decision id in the capability.
- [FR-5] Enforce content-hash verification by recomputing SHA-256 over the rendered ADR content immediately before mutation.
- [FR-6] Enforce PoC default TTL of 10 minutes, configurable through repository/global settings later.
- [FR-7] Record capability consumption atomically with mutation result and audit event.
- [FR-8] Support idempotent retry only for the same decision id and same target mutation fingerprint.
- [FR-9] Expose `ApprovalBoundMutationService` as the only write-side path to `ArchitectureGraphStore` and the consumption boundary for downstream publish feature 011.
- [FR-10] Provide audit queries that join review decision, capability minting, validation failure, consumption, graph mutation, and downstream publication by `decision_id`.
- [FR-11] Emit metadata-only observability events through the existing `Observability` port; never log raw drafts, reviewer comments, prompts, or diffs by default.

## ApprovedReviewDecision Contract

`ApprovedReviewDecision` is a short-lived, one-shot capability object, not a permanent credential and not a graph record.

Required fields:

| Field | Meaning |
|---|---|
| `decision_id: UUID` | Stable capability id and audit join key. |
| `repository: RepositoryIdentity` | Repository scope; must match draft, structural change, mutation target, graph call, and publish target. |
| `reviewer_id: str` | Human reviewer identity from feature 009 PoC auth. |
| `workflow_thread_id: str` | Feature 015 thread/checkpoint identity for traceability only. |
| `review_event_id: UUID` | Durable `ApprovalEvent` id that minted the capability. |
| `adr_draft_id: UUID` | Draft reviewed by the human. |
| `adr_record_id: str` | Stable ADR record id authorized for graph/publish. |
| `adr_draft_content_hash: str` | SHA-256 of the exact rendered ADR content approved by the reviewer. |
| `structural_change_event_id: UUID` | Structural change/evidence lineage being approved. |
| `decision_version: int` | Monotonic version for regenerated drafts for the same change event. |
| `decision_minted_at: datetime` | UTC mint timestamp. |
| `decision_ttl: timedelta` | Default 10 minutes for PoC. |
| `target_mutation_fingerprint: str` | Canonical fingerprint of the authorized mutation set. |
| `consumed_at: datetime | None` | Set only after atomic successful consumption. |

Validation errors: `DecisionExpiredError`, `DecisionAlreadyConsumedError`, `DecisionRepositoryMismatchError`, `DraftContentMismatchError`, `DecisionNotApprovedError`, `TargetMutationMismatchError`, and `AuditDurabilityError`.

## Non-Functional Requirements

- [NFR-1] Fail closed: if audit persistence, hash verification, TTL validation, or consumption recording fails, no authoritative mutation occurs.
- [NFR-2] Audit records are append-only and durable in the workflow-service write-side store, distinct from LangGraph checkpoint tables.
- [NFR-3] All methods are repository-scoped and deterministic under replay.
- [NFR-4] Tests use project-local SQLite fixtures and fakes; no live GitHub, Claude, LangSmith, browser, or external graph database is required.
- [NFR-5] Boundary tests prove MCP and review UI cannot mutate graph state directly.
- [NFR-6] Observability is metadata-only and compatible with `..\..\architecture.md#cross-cutting` default-deny raw export.

## Out of Scope

- Building or changing the feature 009 review UI, templates, accessibility behavior, or form nonce implementation.
- Owning LangGraph checkpoint persistence, graph topology, or replay state; that remains feature 015.
- Implementing LlamaIndex graph persistence or read queries; that remains feature 007.
- Publishing ADR Markdown to GitHub; feature 011 consumes this feature's capability/audit contract.
- Multi-user RBAC, reviewer assignment, notifications, approval quorum, or enterprise identity.
- Replacing SQLite with Postgres or adding external compliance tooling.

## Success Criteria

- [ ] All review outcomes are durably recorded as `ApprovalEvent` rows.
- [ ] Approved outcomes mint an `ApprovedReviewDecision`; reject/defer never do.
- [ ] Capabilities expire after the default 10-minute TTL unless configured otherwise.
- [ ] A capability authorizes exactly one target mutation, with idempotent retry only for the same fingerprint.
- [ ] Content hash mismatch prevents graph mutation and records an audit failure.
- [ ] `ApprovalBoundMutationService` is the only path to write-side graph mutation and the documented consumption boundary for feature 011.
- [ ] Audit durability remains independent from feature 015 checkpoint durability.
- [ ] Metadata-only telemetry and tests enforce no raw draft/comment leakage.

## Resolved Defaults / Open Questions

Autopilot resolves all planning questions for readiness:

- TTL default: 10 minutes, matching `..\..\architecture.md#service-boundaries`.
- Hash algorithm: SHA-256 over canonical UTF-8 rendered ADR Markdown after line-ending normalization to LF.
- PoC reviewer id: the single configured UI reviewer id from feature 009.
- Audit store: workflow-service-owned SQLite tables, separate from feature 015 checkpointer tables.
- Publication boundary: feature 011 must consume `decision_id`/capability through this feature's authorized mutation boundary; direct GitHub publication without decision linkage is invalid.
