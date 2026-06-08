# Outline: adr-publish-back-github

## Slice Summary

Feature 011 is planned as 5 independently testable vertical slices. Each slice keeps publication behind feature 010's approval boundary and feature 003's SCM provider seam.

## Vertical Slices

### Slice S011-01 — Publication policy and target resolution

Resolve `RepositoryConfig.adr_publication_policy`, target branch, path template, content hash, and publication fingerprint for an approved ADR request.

**Independently testable by:** pure service tests for enabled/disabled policies, default `docs\adr\NNNN-<slug>.md`, repository mismatch, and fingerprint stability.

### Slice S011-02 — Approval-bound publication audit and idempotency records

Persist publication intent/result records keyed by `decision_id` and require feature 010 validation before any provider write.

**Independently testable by:** fake approval-service tests proving no SCM call occurs without valid capability and same-fingerprint retries return prior results.

### Slice S011-03 — ADR slugging, numbering, and path allocation

Slug titles, scan configured ADR directory, allocate the next `NNNN`, detect existing same-decision markers, and handle path conflicts.

**Independently testable by:** fake SCM listing tests covering empty directories, existing numeric files, gaps, malformed names, conflicts, and marker detection.

### Slice S011-04 — GitHub provider contents commit through SCM port

Commit approved ADR Markdown through feature 003's provider seam with decision-linked commit metadata and bounded conflict retry.

**Independently testable by:** fake `SCMProvider`/HTTP-client tests for create success, permission failure, branch conflict refresh, and commit SHA recording.

### Slice S011-05 — Workflow handoff, boundary tests, and observability

Wire publish-back into the approved workflow handoff, emit metadata-only observability, and prove MCP/read-side code cannot publish.

**Independently testable by:** workflow integration tests from approved ADR to publication result plus import/boundary tests and audit query checks by `decision_id`.

## Machine-Readable Slice List

```yaml
feature_id: "011"
feature_name: adr-publish-back-github
slice_count: 5
slices:
  - id: S011-01
    name: publication-policy-and-target-resolution
    task_ids: [T011-S1-001, T011-S1-002, T011-S1-003]
    depends_on: []
    test_focus: policy-target-fingerprint
  - id: S011-02
    name: approval-bound-publication-audit-and-idempotency
    task_ids: [T011-S2-001, T011-S2-002, T011-S2-003, T011-S2-004]
    depends_on: [S011-01]
    test_focus: approval-bound-idempotency
  - id: S011-03
    name: adr-slugging-numbering-and-path-allocation
    task_ids: [T011-S3-001, T011-S3-002, T011-S3-003, T011-S3-004]
    depends_on: [S011-02]
    test_focus: numbering-and-conflicts
  - id: S011-04
    name: github-provider-contents-commit-through-scm-port
    task_ids: [T011-S4-001, T011-S4-002, T011-S4-003, T011-S4-004]
    depends_on: [S011-03]
    test_focus: provider-commit-contract
  - id: S011-05
    name: workflow-handoff-boundary-tests-and-observability
    task_ids: [T011-S5-001, T011-S5-002, T011-S5-003, T011-S5-004]
    depends_on: [S011-04]
    test_focus: end-to-end-publication-boundary
```
