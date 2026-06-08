# Implementation Outline: hitl-review-ui

## Slice Strategy
Feature 009 is split into 6 independently testable vertical slices. Each slice keeps production scope limited to planning target code and preserves the 008/015/010 boundaries.

## Slices

### SL-001 — Pending review gateway and view model
Create the typed UI-facing view model and gateway around feature 015's pending review payload. This slice proves that a `ReviewRequestPayload` can be transformed into renderable data without redefining workflow state.

**Independently testable by:** pure model/gateway tests with fake pending review payloads.

### SL-002 — Accessible draft/evidence review page
Add the GET route and Jinja2 template that renders repository/event/draft/evidence/confidence/provisional status with semantic HTML.

**Independently testable by:** ASGI GET test and template semantics assertions for landmarks, headings, labels, and evidence sections.

### SL-003 — Approve and reject resume actions
Implement POST handlers for approve unchanged and reject with reason, including token/nonce protection and feature 015 resume command submission.

**Independently testable by:** route tests asserting emitted `ReviewResumeCommand` and no approval capability.

### SL-004 — Edit and approve-after-edit flow
Add editable draft textarea, action-specific validation, edited content hash calculation, and validation-error rendering that preserves submitted content.

**Independently testable by:** validation/hash tests and POST tests for approve-after-edit success/failure.

### SL-005 — Defer, status, and error states
Add defer handling and accessible status pages for submitted, not-found/expired, unauthorized, and validation-failed states.

**Independently testable by:** route/template tests for each state and focus/error metadata.

### SL-006 — Accessibility, telemetry, and boundary hardening
Add explicit accessibility regression checks, metadata-only observability events, and boundary tests proving no graph writes, no capability minting, no Claude/GitHub calls, and no raw draft/comment telemetry.

**Independently testable by:** test suite over templates, fake observability, and forbidden dependency fakes.

## Machine-Readable Slice List
```yaml
feature_id: '009'
feature_name: hitl-review-ui
slice_count: 6
slices:
  - id: SL-001
    name: pending-review-gateway-view-model
    task_ids: [T-001, T-002, T-003]
    depends_on: []
    contracts: ['008:ADRDraft provisional fields', '015:ReviewRequestPayload']
  - id: SL-002
    name: accessible-draft-evidence-page
    task_ids: [T-004, T-005, T-006]
    depends_on: [SL-001]
    contracts: ['015:pending review lookup']
  - id: SL-003
    name: approve-reject-resume-actions
    task_ids: [T-007, T-008, T-009]
    depends_on: [SL-001, SL-002]
    contracts: ['015:ReviewResumeCommand', '010:no capability minted here']
  - id: SL-004
    name: edit-approve-after-edit-flow
    task_ids: [T-010, T-011, T-012]
    depends_on: [SL-003]
    contracts: ['008:content hash compatibility', '015:edited resume command']
  - id: SL-005
    name: defer-status-error-states
    task_ids: [T-013, T-014, T-015]
    depends_on: [SL-003]
    contracts: ['015:defer/rejection terminal routing']
  - id: SL-006
    name: accessibility-telemetry-boundary-hardening
    task_ids: [T-016, T-017, T-018]
    depends_on: [SL-002, SL-004, SL-005]
    contracts: ['architecture:cross-cutting', 'architecture:anti-patterns']
```

## Slice Consistency Notes
- Slice count is 6 everywhere.
- Task ids are unique and contiguous from T-001 through T-018.
- Every slice has at least one direct test path.
- Feature 010 boundary is explicitly enforced in SL-003 and SL-006.
