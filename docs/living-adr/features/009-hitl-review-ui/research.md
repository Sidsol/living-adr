# Research: hitl-review-ui

## Sources Read
- `..\..\vision.md`
- `..\..\domain-research.md`
- `..\..\architecture.md`
- `..\..\feature-map.md`
- `..\..\roadmap.md`
- `..\008-claude-adr-drafting-capability\spec.md`
- `..\008-claude-adr-drafting-capability\intent.md`
- `..\015-workflow-orchestration-checkpointing\spec.md`
- `..\015-workflow-orchestration-checkpointing\intent.md`

## Feature Brief Grounding
Feature map row 009 defines `hitl-review-ui` as TH-03, P1, estimated 6 slices, depends on `[008, 015]`, and serializes before 010. Its brief requires a server-rendered FastAPI/Jinja2 review surface with evidence citations, confidence, alternatives/consequences, approve/edit/reject actions, semantic HTML, keyboard accessibility, and single-user PoC token protection.

Roadmap M4 places 009 between Claude drafting (008) and approval capability/audit durability (010). Therefore 009 is a UI and resume-command feature, not an authority or persistence feature.

## Domain Findings Relevant to HITL Review
- Domain research identifies HITL as a workflow where humans approve, edit, reject, label, or resume automated work; LangGraph interrupts and code-review workflows are cited prior art.
- Common failure mode FM-20 is HITL rubber-stamping and approval fatigue. The UI must expose enough evidence, confidence, alternatives, and consequences to make approval meaningful.
- FM-06 after-the-fact hallucinated rationale and FM-19 PR-summary overtrust mean the page must label generated rationale as provisional and cite concrete evidence instead of presenting model text as truth.
- FM-13 excessive agency and FM-23 docs-as-code without review gates require keeping authoritative mutation behind downstream approval capability enforcement.
- FM-21 trace leakage means review comments and draft bodies are sensitive until approved and should not appear in default telemetry.

## Architecture Findings
- `..\..\architecture.md#tech-stack` selects FastAPI + Jinja2 for the HITL UI and explicitly avoids SPA cost for the PoC.
- `..\..\architecture.md#service-boundaries` makes `workflow-service` own HITL state/UI, while `ApprovalBoundMutationService` and graph writes remain outside this feature.
- `..\..\architecture.md#data-model` distinguishes provisional `ADRDraft`, human `ApprovalEvent`, and downstream `ApprovedReviewDecision` capability. This feature presents/captures review intent only.
- `..\..\architecture.md#cross-cutting` requires local single-user UI token protection, metadata-only traces, prompt-injection caution, and accessibility.
- `..\..\architecture.md#anti-patterns` explicitly calls for concise evidence, confidence, alternatives, and edit/reject paths.
- `..\..\architecture.md#deployment` keeps the PoC local/two-process and does not justify adding a frontend service.

## Dependency Contract: Feature 008
Feature 008 produces a provisional ADR draft through Feature 015's draft node. Its spec requires content hash, citations, model metadata, provisional status, and no authoritative mutations. Feature 009 must render that draft exactly as a review target and must not fetch context directly from Claude, SCM, or graph internals.

Important constraints inherited from 008:
- Drafts are provisional and inert until downstream HITL approval.
- Normal tests use fakes only; no real Anthropic calls.
- Raw prompts, diffs, Claude responses, and pre-approval drafts are excluded from telemetry by default.

## Dependency Contract: Feature 015
Feature 015 owns the durable LangGraph graph, SQLite checkpointer, and interrupt/resume semantics. It defines the HITL seam:
- `HITLGateNode.__call__(state) -> Interrupt[ReviewRequestPayload]`
- Resume with `ReviewResumeCommand`
- Interrupt payload includes repository, event key, draft id/hash, draft preview/ref, evidence ids, confidence, and allowed actions.
- Resume command includes action, optional edited draft content/hash, reviewer id, and optional `ApprovedReviewDecision` capability minted by feature 010.

Feature 009 should implement route/template/gateway code around this seam only. It must not own graph topology, checkpointing, replay, or mutation routing.

## UI Shape Implications
The review surface should have:
1. Pending review summary: repository, event key, thread id, draft id/hash, generated timestamp if available.
2. Draft panel: Markdown rendered safely or shown in textarea for edit mode; visible provisional warning.
3. Evidence panel: citation ids/labels, source paths or summaries when present, confidence as text plus visual indicator.
4. Decision panel: approve unchanged, edit and approve, reject with reason, defer with optional reason.
5. Result/error states: submitted, validation failed, unauthorized, missing/expired review.

## Accessibility Findings
Server-rendered HTML is compatible with accessible-by-default controls if implemented with semantic forms. Requirements should emphasize landmarks, headings, labels, fieldsets, error summaries, `aria-describedby` for validation messages, keyboard focus management, visible focus styles, and avoiding color-only confidence/error signals. ARIA should supplement, not replace, semantic HTML.

## Risks and Mitigations
| Risk | Mitigation |
|---|---|
| Reviewer rubber-stamps model output | Put evidence, confidence, alternatives, consequences, and provisional warnings before the action controls. |
| UI accidentally mints authority | Keep only `ReviewResumeCommand` construction here; feature 010 owns capabilities. Add tests asserting `approved_decision is None` from UI-only approval. |
| Seam drift with feature 015 | Wrap review interactions in a small `ReviewWorkflowGateway` that depends on 015 types and has contract tests. |
| Raw draft/comment leakage | Use metadata-only telemetry and avoid logging request bodies. |
| Accessibility regressions | Add template tests for labels, heading hierarchy, fieldsets, error associations, and focus targets. |
| CSRF/replay of form posts | Use a signed per-review nonce in addition to local UI token. |

## Planning Conclusion
The selected plan should implement a small FastAPI/Jinja2 package under `workflow-service`/`hitl`, with typed adapters to feature 015's pending-review and resume services. It must make the review meaningful and accessible while deliberately stopping before approval capability minting, audit durability, and graph mutation.
