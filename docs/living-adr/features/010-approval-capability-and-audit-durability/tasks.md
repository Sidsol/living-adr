# Tasks: approval-capability-and-audit-durability

## Story: Durable review event capture (S010-01)

- [x] **T010-S1-001 — Defining approval event models**  
  Create domain models for `ApprovalEvent`, outcomes, reviewer identity, draft references, and audit timestamps.
- [x] **T010-S1-002 — Creating durable approval repository**  
  Add append-only approval/audit repository storage separate from feature 015 checkpoint tables.
- [x] **T010-S1-003 — Recording all review outcomes**  
  Persist approve, approve-after-edit, reject, and defer commands from feature 009/015 with no capability for non-approved outcomes.

## Story: ApprovedReviewDecision minting and content hash (S010-02)

- [x] **T010-S2-001 — Defining approved decision contract**  
  Implement the full `ApprovedReviewDecision` field contract needed by graph mutation and feature 011 publish-back.
- [x] **T010-S2-002 — Implementing canonical ADR hashing**  
  Normalize rendered ADR Markdown to UTF-8/LF and compute SHA-256 consistently.
- [x] **T010-S2-003 — Minting approved capabilities**  
  Mint capabilities for approve and approve-after-edit only, selecting original or edited content hash correctly.

## Story: TTL and validation failures (S010-03)

- [x] **T010-S3-001 — Adding TTL validation**  
  Enforce the 10-minute PoC default and inject clocks for expiry tests.
- [x] **T010-S3-002 — Adding repository and target validation**  
  Reject repository mismatch, non-approved states, and target mutation fingerprint mismatch.
- [x] **T010-S3-003 — Detecting draft content tampering**  
  Re-hash current rendered ADR content before mutation and fail closed on mismatch.

## Story: One-shot consumption and idempotent retry (S010-04)

- [x] **T010-S4-001 — Designing consumption records**  
  Define durable consumption rows keyed by `decision_id`, target fingerprint, result, and timestamp.
- [x] **T010-S4-002 — Recording atomic consumption**  
  Reserve/finalize consumption transactionally with mutation result linkage.
- [x] **T010-S4-003 — Supporting idempotent retry**  
  Return the prior result for same decision id and same target mutation fingerprint.
- [x] **T010-S4-004 — Rejecting decision reuse**  
  Raise `DecisionAlreadyConsumedError` for same decision id with a different target fingerprint.

## Story: Append-only audit durability and SM-05 queries (S010-05)

- [x] **T010-S5-001 — Writing audit event taxonomy**  
  Define audit event types for review, minting, validation failure, consumption, mutation, and publish placeholder.
- [x] **T010-S5-002 — Persisting validation failure audits**  
  Record typed failure audits without raw draft/comment leakage.
- [x] **T010-S5-003 — Building SM05 audit queries**  
  Provide query helpers showing all authoritative mutations are linked to an approved decision.
- [x] **T010-S5-004 — Separating audit from checkpoints**  
  Add tests proving audit records survive independently of feature 015 checkpoint reset/replay behavior.

## Story: ApprovalBoundMutationService graph boundary (S010-06)

- [x] **T010-S6-001 — Defining mutation service interface**  
  Create the single authoritative mutation service entrypoint and result DTO.
- [x] **T010-S6-002 — Delegating graph writes through service**  
  Call `ArchitectureGraphStore` only after capability validation and audit reservation.
- [x] **T010-S6-003 — Preventing direct graph mutation**  
  Add boundary tests proving workflow/MCP code cannot bypass the service.
- [x] **T010-S6-004 — Preserving adapter neutrality**  
  Keep all code dependent on domain ports, not feature 007 LlamaIndex internals.

## Story: Workflow and publish consumption contract (S010-07)

- [x] **T010-S7-001 — Wiring workflow approval node**  
  Integrate minting into feature 015 resume path without owning checkpointing.
- [x] **T010-S7-002 — Passing capability to mutation handoff**  
  Ensure approved workflow state carries the capability to mutation handoff and reject/defer paths do not.
- [x] **T010-S7-003 — Documenting feature011 publish boundary**  
  Add contract tests/docs requiring feature 011 to consume `ApprovedReviewDecision` and `decision_id` audit linkage.
- [x] **T010-S7-004 — Verifying end-to-end approval durability**  
  Run an integration scenario from review command through audit, capability, validation, consumption, and mutation result.

## Counts

```yaml
feature_id: "010"
slice_count: 7
task_count: 25
slices:
  S010-01: 3
  S010-02: 3
  S010-03: 3
  S010-04: 4
  S010-05: 4
  S010-06: 4
  S010-07: 4
```
