# CRISPY Checklist: approval-capability-and-audit-durability

## Planning Completeness

- [ ] `spec.md` defines one-shot, TTL, content-hash binding, durable audit persistence, and `ApprovalBoundMutationService` scope.
- [ ] `research.md` binds explicitly to feature 009, 007, and 015 without redefining their contracts.
- [ ] `intent.md` references `..\..\architecture.md#service-boundaries`, `#data-model`, `#tech-stack`, `#cross-cutting`, `#anti-patterns`, `#deployment`, and `#repositories`.
- [ ] `outline.md`, `plan.md`, `tasks.md`, and `implementation-manifest.yaml` all declare 7 slices.
- [ ] Task IDs are unique and consistently mapped to slices.

## Contract Gates

- [ ] `ApprovedReviewDecision` contract includes `decision_id`, repository, reviewer, draft id, ADR id, content hash, structural change id, decision version, minted timestamp, TTL, target mutation fingerprint, and consumption state.
- [ ] Feature 009 remains the reviewer decision UI only; it does not mint capabilities.
- [ ] Feature 015 remains workflow checkpoint/resume only; audit durability is separate.
- [ ] Feature 007 remains graph adapter only; approval consumption is not adapter-owned.
- [ ] Feature 011 must consume this feature's capability/audit contract for publish-back.

## Quality Gates for Future Implementation

- [ ] Reject/defer outcomes are audited and never mint an `ApprovedReviewDecision`.
- [ ] Approve/approve-after-edit outcomes mint exactly one capability per decision version.
- [ ] Expired decisions fail closed before graph or publication mutation.
- [ ] Content hash mismatch raises `DraftContentMismatchError` and records failure audit.
- [ ] Same `decision_id` with same target fingerprint is idempotent; different fingerprint is rejected.
- [ ] `ApprovalBoundMutationService` is the only write path to `ArchitectureGraphStore`.
- [ ] Audit tables are append-only and separate from feature 015 checkpoint tables.
- [ ] Observability excludes raw drafts, reviewer comments, prompts, and diffs by default.
- [ ] Tests use fakes/project-local SQLite and no live GitHub, Claude, LangSmith, browser, or external graph database.

## Anti-Pattern Checks

- [ ] No direct graph writes from workflow nodes, UI routes, MCP server, or publish-back code.
- [ ] No approval represented only as a boolean flag.
- [ ] No audit fact stored only in LangGraph checkpoint state.
- [ ] No LlamaIndex-specific import or type leaks into approval code.
- [ ] No multiple-authoritative-mutation use of a single capability.
- [ ] No post-approval content mutation without re-review.

## Readiness Decision

- [ ] Manifest has `ready: true`.
- [ ] Open questions are resolved with documented defaults.
- [ ] No production/application code is created by this planning run.
