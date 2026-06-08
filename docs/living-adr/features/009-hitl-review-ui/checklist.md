# CRISPY Checklist: hitl-review-ui

## Contract Gates
- [ ] Consumes feature 008 provisional `ADRDraft` content/hash/citations/model metadata without redefining drafting.
- [ ] Renders feature 015 `ReviewRequestPayload` without redefining workflow state or graph topology.
- [ ] Submits feature 015 `ReviewResumeCommand` for approve, approve-after-edit, reject, and defer.
- [ ] Does not mint `ApprovedReviewDecision`; feature 010 owns capability minting and audit durability.
- [ ] Does not call graph store, approval-bound mutation service, Claude, GitHub provider, or MCP server.

## Functional Gates
- [ ] Pending review page shows repository, event key, draft id/hash, draft content/preview, evidence/citations, confidence, and allowed actions.
- [ ] Approve unchanged submits original draft hash.
- [ ] Approve-after-edit validates content, computes edited hash, and preserves failed edits.
- [ ] Reject requires a reason.
- [ ] Defer accepts an optional reason and resumes through the seam.
- [ ] Missing/expired/unauthorized states are safe and user-readable.

## Accessibility Gates
- [ ] Semantic landmarks and heading hierarchy are present.
- [ ] All form controls have visible labels.
- [ ] Action controls are grouped with `fieldset`/`legend` or equivalent semantics.
- [ ] All actions are keyboard reachable with visible focus.
- [ ] Error summary links to invalid fields and errors are connected via `aria-describedby`.
- [ ] Status/error messages have an appropriate focus/announcement target.
- [ ] Color is not the sole indicator of confidence, warning, or error state.

## Security / Privacy Gates
- [ ] All review routes require local UI token authentication.
- [ ] State-changing POSTs require signed per-review nonce.
- [ ] Draft bodies, reviewer comments, prompts, diffs, and Claude responses are not logged or traced by default.
- [ ] Draft content is never placed in query strings.
- [ ] Untrusted Markdown/model output is rendered safely.

## Test Gates
- [ ] View model and validation tests pass.
- [ ] Gateway contract tests prove compatibility with feature 015 payload/command shapes.
- [ ] Route tests cover GET, approve, approve-after-edit, reject, defer, unauthorized, missing, and validation failure.
- [ ] Template accessibility tests cover labels/headings/fieldsets/errors/focus targets.
- [ ] Boundary tests fail on capability minting, graph writes, Claude/GitHub calls, or raw telemetry.
- [ ] Existing project test and lint commands pass after implementation.

## Documentation / Planning Gates
- [ ] Slice count is 6 across `outline.md`, `plan.md`, `tasks.md`, and `implementation-manifest.yaml`.
- [ ] Task ids are unique and match across `plan.md`, `tasks.md`, and manifest.
- [ ] Windows backslash paths are used inside YAML path values.
- [ ] `implementation-manifest.yaml` parses as valid YAML and has `ready: true`.
