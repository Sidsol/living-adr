# Outline: approval-capability-and-audit-durability

## Slice Summary

Feature 010 is planned as 7 independently testable vertical slices. Each slice preserves the same boundaries: feature 009 captures human intent, feature 015 owns workflow checkpointing, feature 007 implements graph ports, and feature 010 owns approval/audit durability plus the authorized mutation boundary.

## Vertical Slices

### Slice S010-01 — Durable review event capture

Persist every review outcome from `ReviewResumeCommand` as an append-only `ApprovalEvent` without minting authority for rejected/deferred outcomes.

**Independently testable by:** repository tests that submit approve, approve-after-edit, reject, and defer commands and verify durable audit rows after reopen.

### Slice S010-02 — ApprovedReviewDecision minting and content hash contract

Define and mint `ApprovedReviewDecision` for approved outcomes only, binding to original or edited canonical ADR content hash.

**Independently testable by:** pure service tests for approve vs reject/defer, edited hash selection, required fields, and serialization.

### Slice S010-03 — TTL and validation failures

Validate capability freshness, repository scope, approval state, and draft content hash before mutation, failing closed with typed errors and audit entries.

**Independently testable by:** clock-controlled validation tests for expired/current decisions, repository mismatch, and content tampering.

### Slice S010-04 — One-shot consumption and idempotent retry

Record consumption atomically, allow same-fingerprint retry to return the prior result, and reject same-decision different-fingerprint reuse.

**Independently testable by:** SQLite transaction tests with repeated calls, simulated restart, and collision cases.

### Slice S010-05 — Append-only audit durability and SM-05 queries

Provide durable audit linkage across review event, minting, validation failure, consumption, mutation result, and downstream publication placeholder.

**Independently testable by:** audit query tests that prove decision/mutation joins by `decision_id` and separation from feature 015 checkpoint tables.

### Slice S010-06 — ApprovalBoundMutationService graph boundary

Implement the service as the only code path to call `ArchitectureGraphStore` write methods, delegating to feature 007's adapter through domain ports only.

**Independently testable by:** fake graph store tests proving no call occurs without valid capability and direct writes are not exposed to workflow/MCP code.

### Slice S010-07 — Workflow and feature-011 consumption contract

Wire the approval service into feature 015's resume/mutation handoff seam and document/test the downstream feature 011 publish-back consumption boundary.

**Independently testable by:** workflow integration tests with stub graph/publish target and manifest contract tests for `ApprovedReviewDecision` fields.

## Machine-Readable Slice List

```yaml
feature_id: "010"
feature_name: approval-capability-and-audit-durability
slice_count: 7
slices:
  - id: S010-01
    name: durable-review-event-capture
    task_ids: [T010-S1-001, T010-S1-002, T010-S1-003]
    depends_on: []
    test_focus: approval-event-repository
  - id: S010-02
    name: approved-decision-minting-and-content-hash
    task_ids: [T010-S2-001, T010-S2-002, T010-S2-003]
    depends_on: [S010-01]
    test_focus: capability-minting-contract
  - id: S010-03
    name: ttl-and-validation-failures
    task_ids: [T010-S3-001, T010-S3-002, T010-S3-003]
    depends_on: [S010-02]
    test_focus: fail-closed-validation
  - id: S010-04
    name: one-shot-consumption-and-idempotent-retry
    task_ids: [T010-S4-001, T010-S4-002, T010-S4-003, T010-S4-004]
    depends_on: [S010-03]
    test_focus: atomic-consumption
  - id: S010-05
    name: append-only-audit-durability-and-sm05-queries
    task_ids: [T010-S5-001, T010-S5-002, T010-S5-003, T010-S5-004]
    depends_on: [S010-04]
    test_focus: audit-query-durability
  - id: S010-06
    name: approval-bound-mutation-service-graph-boundary
    task_ids: [T010-S6-001, T010-S6-002, T010-S6-003, T010-S6-004]
    depends_on: [S010-05]
    test_focus: graph-boundary-enforcement
  - id: S010-07
    name: workflow-and-publish-consumption-contract
    task_ids: [T010-S7-001, T010-S7-002, T010-S7-003, T010-S7-004]
    depends_on: [S010-06]
    test_focus: workflow-feature011-contract
```
