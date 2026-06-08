# Research: approval-capability-and-audit-durability

## Sources Read

- `..\..\vision.md`
- `..\..\domain-research.md`
- `..\..\architecture.md`
- `..\..\feature-map.md`
- `..\..\roadmap.md`
- `..\007-llamaindex-property-graph-adapter\spec.md`
- `..\007-llamaindex-property-graph-adapter\intent.md`
- `..\009-hitl-review-ui\spec.md`
- `..\009-hitl-review-ui\intent.md`
- `..\015-workflow-orchestration-checkpointing\spec.md`
- `..\015-workflow-orchestration-checkpointing\intent.md`

## Feature Context

Feature 010 sits on the M4 critical path after feature 009 and before feature 011. The project vision requires zero unapproved authoritative mutations (SM-05). Architecture makes `ApprovedReviewDecision` the capability that turns a human review into authority, and `ApprovalBoundMutationService` the only component permitted to call write-side graph ports. Feature-map lines for 010 specify durable `ApprovalEvent` recording, one-shot consumption, TTL expiry, content-hash pinning, idempotent retry semantics, mutation/audit linkage, and rejection/edit lifecycle state.

## Dependency Binding Findings

### Feature 009 — HITL Review UI

Feature 009 captures reviewer intent but deliberately does not mint authority. It submits feature 015 `ReviewResumeCommand` values for `approve`, `approve_after_edit`, `reject`, and `defer`. The command carries reviewer id, original or edited draft content/hash, and `approved_decision: None` until feature 010 participates.

Feature 010 must therefore bind to 009 by consuming the review action and content/hash exactly as submitted. It must not add UI behavior or re-fetch evidence for display. It should validate that approve-after-edit has edited content and an edited hash before minting.

### Feature 007 — LlamaIndex Graph Adapter

Feature 007 implements graph ports and read snapshots, but explicitly leaves durable approval semantics to feature 010. Its adapter should receive only domain types and valid decisions through the `ApprovalBoundMutationService` boundary. Feature 010 must not depend on LlamaIndex internals; it validates approvals before graph writes and lets the adapter persist approved graph projections with decision/provenance metadata.

Feature 010 should also preserve graph swappability: validation and audit records are domain-level behavior independent of whether the store is LlamaIndex, Neo4j, RDF, or another adapter.

### Feature 015 — Workflow Orchestration Checkpointing

Feature 015 owns LangGraph checkpoint durability for in-flight workflow state, interrupt/resume, deterministic thread id, and replay. It explicitly does not own `ApprovalEvent` persistence, capability minting, TTL, one-shot consumption, or audit completeness.

Feature 010's audit store must be separate from checkpointer tables. The workflow may carry references to `ApprovedReviewDecision`, but the authoritative record of approval and consumption lives in feature 010 audit tables. Checkpoint replay can retry nodes, but feature 010 must ensure retries do not duplicate mutations.

## Domain and Architecture Constraints

- `..\..\architecture.md#service-boundaries`: Graph mutations are constructively impossible without `ApprovedReviewDecision`; MCP cannot mutate.
- `..\..\architecture.md#data-model`: `ApprovalEvent` / `ApprovedReviewDecision` is separate from provisional `ADRDraft`; approved ADR records are canonical rationale, graph nodes are projections.
- `..\..\architecture.md#cross-cutting`: mutation flow is approval-bound, transactional, audit-linked, and metadata-only in observability.
- `..\..\architecture.md#anti-patterns`: mitigates FM-13 excessive agency, FM-20 rubber stamping, and FM-23 docs-as-code without review gates.
- `..\..\architecture.md#deployment`: PoC persistence is workflow-service single-writer SQLite/WAL; same host with MCP read-only process.

## Key Design Implications

1. **Approval is a capability, not a status string.** A plain `approved` flag is insufficient because downstream mutations need TTL, hash binding, repository scope, one-shot consumption, and audit linkage.
2. **Audit and checkpoint durability differ.** Checkpoints answer "where did the workflow pause?" Audit answers "who approved what exact content, when, and what mutation consumed it?" These must survive different lifecycle operations.
3. **Content hash is the tamper boundary.** The hash must cover canonical rendered ADR Markdown after edit handling, not merely draft id or evidence id.
4. **Idempotency must be mutation-fingerprint aware.** Replaying a successful mutation for the same target should be safe; using the same approval for a new target must fail.
5. **Feature 011 needs a stable contract.** Publish-back must consume `ApprovedReviewDecision`/`decision_id` and record publication audit linkage, not invent a separate approval model.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Workflow replay causes duplicate graph mutation | Atomic consumption plus target mutation fingerprint and stored prior result. |
| Approval outlives reviewed content | Short TTL and re-hash immediately before mutation. |
| Edited draft hash differs across platforms | Canonical UTF-8 with LF line endings before SHA-256. |
| Audit store becomes a second checkpoint store | Separate tables/repositories and language: audit events are immutable business facts; checkpoints are resumable orchestration state. |
| Downstream code bypasses `ApprovalBoundMutationService` | Boundary tests, package wiring, and no direct `ArchitectureGraphStore` injection into workflow nodes except inside service. |
| Graph adapter-specific leakage | Keep feature 010 on feature 006/007 domain ports only. |

## Planning Assumptions

- The repository is greenfield; no production code exists yet in `C:\repos\living-adr`.
- Feature 006 has established domain ports before this implementation begins.
- Feature 009 provides a validated review action and reviewer id.
- Feature 015 provides deterministic workflow thread id and resume/replay services.
- Feature 007 provides a graph adapter behind `ArchitectureGraphStore` but not approval durability.

## Research Conclusion

Feature 010 should be implemented as a domain/audit boundary inside `workflow-service`: a durable approval repository, capability minting service, validation/consumption repository, and `ApprovalBoundMutationService`. It should not redefine UI, graph adapter, or workflow checkpoint contracts. The selected shape directly enforces SM-05 and creates the contract feature 011 can rely on for publish-back.
