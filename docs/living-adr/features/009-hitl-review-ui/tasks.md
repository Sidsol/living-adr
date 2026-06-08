# Tasks: hitl-review-ui

## Story: Reviewer sees pending ADR draft (SL-001, SL-002)
- [x] T-001 — Defining review view models: create `PendingReviewPage`, action constants, validation-error structures, and tests.
- [x] T-002 — Creating review workflow gateway: define fakeable gateway protocol/adapter for feature 015 pending review and resume services.
- [x] T-003 — Mapping pending payload to page model: map `ReviewRequestPayload` + feature 008 draft fields into renderable data.
- [x] T-004 — Adding review GET route: add protected GET route for pending review pages using fake gateway tests.
- [x] T-005 — Rendering draft evidence template: build semantic Jinja2 template for summary, draft, evidence, confidence, and actions.
- [x] T-006 — Styling accessible review states: add minimal CSS for focus, errors, warnings, and confidence without color-only cues.

## Story: Reviewer approves or rejects draft (SL-003)
- [x] T-007 — Protecting review forms: implement UI token guard and signed per-review nonce validation.
- [x] T-008 — Submitting approve command: submit unchanged approval as `ReviewResumeCommand(action="approve")` with no capability minted.
- [x] T-009 — Submitting reject command: validate rejection reason and submit `ReviewResumeCommand(action="reject")` without mutation handoff authority.

## Story: Reviewer edits before approving (SL-004)
- [x] T-010 — Validating edited draft content: enforce non-empty edited Markdown with required ADR sections and inline errors.
- [x] T-011 — Hashing edited draft content: compute deterministic SHA-256 compatible with feature 008/015 hash expectations.
- [x] T-012 — Submitting approve-after-edit command: preserve edits on errors and submit edited content/hash on success.

## Story: Reviewer defers or sees terminal states (SL-005)
- [x] T-013 — Submitting defer command: submit `ReviewResumeCommand(action="defer")` with optional reason.
- [x] T-014 — Rendering status pages: add submitted, rejected, deferred, and generic status views with accessible focus target.
- [x] T-015 — Handling missing unauthorized states: return safe not-found/expired/unauthorized states without revealing draft content.

## Story: Operator trusts UI boundaries and quality (SL-006)
- [x] T-016 — Testing accessibility quality gates: assert landmarks, headings, labels, fieldsets, `aria-describedby`, error summary, and keyboard-reachable controls.
- [x] T-017 — Emitting metadata-only observability: emit review ids/action/result/latency/error class only; exclude draft/comment bodies.
- [x] T-018 — Enforcing capability and mutation boundary: test no `ApprovedReviewDecision` minting, no graph writes, no Claude/GitHub calls, and no audit durability in 009.

## Machine-Readable Task Summary
```yaml
feature_id: '009'
slice_count: 6
task_count: 18
stories:
  - story: reviewer-sees-pending-adr-draft
    slices: [SL-001, SL-002]
    tasks: [T-001, T-002, T-003, T-004, T-005, T-006]
  - story: reviewer-approves-or-rejects-draft
    slices: [SL-003]
    tasks: [T-007, T-008, T-009]
  - story: reviewer-edits-before-approving
    slices: [SL-004]
    tasks: [T-010, T-011, T-012]
  - story: reviewer-defers-or-sees-terminal-states
    slices: [SL-005]
    tasks: [T-013, T-014, T-015]
  - story: operator-trusts-boundaries-quality
    slices: [SL-006]
    tasks: [T-016, T-017, T-018]
```

## Consistency Checks
- 6 slices match `outline.md`, `plan.md`, and `implementation-manifest.yaml`.
- 18 unique task ids match `plan.md` task graph.
- Every task maps to exactly one slice.

