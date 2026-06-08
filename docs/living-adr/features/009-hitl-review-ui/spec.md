# Feature Specification: hitl-review-ui

## Overview
Feature 009 delivers LivingADR's server-rendered human-in-the-loop review surface for pending ADR drafts. It presents the provisional `ADRDraft` produced by feature 008, including evidence citations, confidence, alternatives, consequences, and provisional-rationale warnings, and captures reviewer approve / edit / reject / defer actions. The UI plugs into feature 015's LangGraph HITL interrupt/resume seam by rendering `ReviewRequestPayload` and submitting `ReviewResumeCommand`.

This feature does **not** mint authoritative approval capabilities, persist durable approval/audit records, mutate the graph, publish ADRs, or redefine workflow orchestration. Feature 010 owns `ApprovalEvent` durability and `ApprovedReviewDecision` minting/consumption.

## User Stories

### [US-1] Review pending ADR draft — Priority: P1
**As a** tech lead reviewer, **I want** to see a pending ADR draft with its evidence and confidence, **so that** I can make an informed review decision.

#### Acceptance Scenarios
- **Given** feature 015 interrupts with a `ReviewRequestPayload`, **When** I open the review page, **Then** I see repository identity, event key, draft id/hash, draft content or preview, evidence ids/citations, confidence, allowed actions, and provisional-status copy.
- **Given** no pending review exists for the requested thread, **When** I open the page, **Then** I receive an accessible not-found/expired state without exposing internals.

### [US-2] Approve without minting authority — Priority: P1
**As a** reviewer, **I want** to approve an unchanged draft, **so that** the paused workflow can resume to the downstream approval-durability feature.

#### Acceptance Scenarios
- **Given** I approve an unchanged draft, **When** the form submits, **Then** the UI sends a feature-015 `ReviewResumeCommand(action="approve")` with reviewer id, draft id, and original hash.
- **Given** feature 010 is not yet implemented, **When** approval is submitted, **Then** no `ApprovedReviewDecision` capability is minted by this feature.

### [US-3] Edit before approval — Priority: P1
**As a** reviewer, **I want** to edit the draft before approving, **so that** missing context or wording issues can be corrected before downstream authority.

#### Acceptance Scenarios
- **Given** I edit the draft body and submit approve-after-edit, **When** the form is validated, **Then** the UI sends `ReviewResumeCommand(action="approve_after_edit")` with edited content and an edited content hash.
- **Given** the edited content is empty or lacks required ADR sections, **When** I submit, **Then** the page returns inline validation errors and preserves my edits.

### [US-4] Reject or defer draft — Priority: P1
**As a** reviewer, **I want** to reject or defer a draft with a reason, **so that** low-quality or premature drafts do not become authoritative context.

#### Acceptance Scenarios
- **Given** I reject a draft, **When** I submit a rejection reason, **Then** the workflow resumes with `ReviewResumeCommand(action="reject")` and no mutation handoff is requested.
- **Given** I defer a draft, **When** I submit an optional reason, **Then** the workflow resumes with `ReviewResumeCommand(action="defer")` or remains pending according to feature 015 routing.

### [US-5] Accessible review experience — Priority: P1
**As a** keyboard or assistive-technology user, **I want** semantic, labeled controls and predictable navigation, **so that** I can complete review without a mouse.

#### Acceptance Scenarios
- **Given** the review page renders, **When** I navigate by keyboard, **Then** focus order follows heading → summary → draft → evidence → actions, visible focus is present, and every control is reachable.
- **Given** validation fails, **When** the page re-renders, **Then** errors are associated with controls and announced through an appropriate live/error region.

### [US-6] PoC token protection and safe telemetry — Priority: P1
**As a** platform operator, **I want** single-user PoC access control and metadata-only observability, **so that** review pages are not publicly exposed and sensitive draft text is not logged by default.

#### Acceptance Scenarios
- **Given** a request lacks the configured UI token, **When** it reaches any review route, **Then** access is denied without revealing draft content.
- **Given** any review page or action occurs, **When** telemetry is emitted, **Then** it contains ids, action, result, latency, and error class only, not raw draft text, comments, prompts, or diffs.

## Functional Requirements
- [FR-1] Render feature 015 `ReviewRequestPayload` fields without changing the payload contract.
- [FR-2] Submit feature 015 `ReviewResumeCommand` for approve, approve-after-edit, reject, and defer actions.
- [FR-3] Consume feature 008's provisional `ADRDraft`/content/hash as review input; do not treat it as authoritative.
- [FR-4] Provide FastAPI routes, Jinja2 templates, form validation, and post/redirect/get behavior for review actions.
- [FR-5] Protect all HITL routes with the local single-user UI token described in `..\..\architecture.md#cross-cutting`.
- [FR-6] Preserve edited draft content on validation failure and compute edited content hash only for submitted edit actions.
- [FR-7] Emit metadata-only observability events through the existing `Observability` seam.
- [FR-8] Never call `ArchitectureGraphStore`, `ApprovalBoundMutationService`, GitHub publication APIs, or Claude from this feature.

## Non-Functional Requirements
- [NFR-1] Accessibility: semantic HTML landmarks/headings/forms, explicit labels, keyboard navigation, visible focus, error association, ARIA only where semantic HTML is insufficient.
- [NFR-2] Security: CSRF-style form token or signed per-review nonce for state-changing POSTs; no draft content in URLs or logs.
- [NFR-3] Testability: route/template tests use fake review gateway and fake workflow resume service; no live LangGraph, GitHub, Claude, graph DB, or browser service required.
- [NFR-4] Simplicity: server-rendered HTML only; progressive enhancement is allowed but SPA-only behavior is out of scope.
- [NFR-5] Boundary discipline: downstream approval minting/audit durability remains feature 010.

## Contract Bindings

### Feature 008 draft input
Feature 009 presents feature 008's provisional draft output: `ADRDraft`/draft reference, Markdown content or preview, `adr_draft_content_hash`, model metadata, citations, and provisional-rationale flag. It does not redefine draft generation, prompt packaging, Claude policy, or graph-context retrieval.

### Feature 015 HITL interrupt/resume seam
Feature 009 renders and submits exactly around feature 015's seam:

```python
ReviewRequestPayload = {
    "repository": RepositoryIdentity,
    "event_key": str,
    "draft_id": str,
    "draft_hash": str,
    "draft_preview_or_ref": str,
    "evidence_ids": tuple[str, ...],
    "confidence": float,
    "allowed_actions": ("approve", "approve_after_edit", "reject", "defer"),
}

ReviewResumeCommand = {
    "action": str,
    "optional_edited_draft_content": str | None,
    "optional_edited_draft_hash": str | None,
    "reviewer_id": str,
    "approved_decision": None,  # populated only by feature 010
}
```

## Out of Scope
- `ApprovedReviewDecision` minting, TTL, one-shot consumption, and durable audit records (feature 010).
- Any graph mutation or `ArchitectureGraphStore` write call.
- ADR publication to GitHub (feature 011).
- Draft generation, Claude calls, prompt validation, or graph-context retrieval (feature 008).
- Workflow graph assembly, checkpoint ownership, or alternate orchestration (feature 015).
- Multi-user RBAC, reviewer assignment, notifications, or enterprise identity.

## Acceptance Criteria
- [ ] Pending review pages render all required draft/evidence/provisional context.
- [ ] Approve, approve-after-edit, reject, and defer actions submit valid `ReviewResumeCommand` payloads.
- [ ] Edited content validation is clear, inline, and preserves input.
- [ ] UI is keyboard accessible and uses semantic HTML with labels and visible focus.
- [ ] Unauthorized requests cannot read or submit reviews.
- [ ] No approval capability is minted and no graph mutation is attempted.
- [ ] Metadata-only observability excludes raw drafts, comments, prompts, and diffs.

## Accessibility Criteria
- [ ] One `main` landmark and a logical `h1`→`h2` heading hierarchy.
- [ ] Form controls have visible labels; grouped radio/actions use `fieldset`/`legend`.
- [ ] Validation errors are linked with `aria-describedby` and summarized near the top.
- [ ] Keyboard users can select each action, edit content, submit, cancel, and return to summary.
- [ ] Focus moves to the error summary after failed validation and to the status message after success.
- [ ] Color is not the only indicator for confidence, warnings, or errors.

## Resolved Defaults / Open Questions
Autopilot resolves all planning ambiguities:
- Default actions: approve, approve-after-edit, reject, defer.
- PoC auth: existing local UI token plus per-review form nonce.
- Reviewer identity: configured single-user id from environment until multi-user feature exists.
- Defer behavior: submit `defer` to feature 015 and leave final lifecycle semantics to the seam; no audit capability is minted here.
- Draft validation default: require non-empty edited Markdown with Title/Status/Context/Decision/Consequences headings.
