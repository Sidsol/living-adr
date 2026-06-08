# Architecture Intent: hitl-review-ui

## Current State
LivingADR's architecture assigns HITL UI to the `workflow-service` and chooses server-rendered FastAPI/Jinja2 for the PoC. Feature 008 produces provisional ADR drafts. Feature 015 owns LangGraph checkpointing and the interrupt/resume seam. Feature 010, not this feature, will mint authoritative approval capabilities and persist audit state.

Architecture anchors:
- `..\..\architecture.md#service-boundaries`: workflow-service owns HITL UI; graph mutation requires downstream approval-bound capability.
- `..\..\architecture.md#data-model`: `ADRDraft` is provisional; `ApprovalEvent`/`ApprovedReviewDecision` are separate downstream authority concepts.
- `..\..\architecture.md#tech-stack`: FastAPI, Jinja2, Python 3.12, pytest, Ruff, SQLite/LangGraph in the workflow service.
- `..\..\architecture.md#cross-cutting`: local UI token, metadata-only traces, untrusted model output, accessibility.
- `..\..\architecture.md#anti-patterns`: avoid rubber-stamping, excessive agency, trace leakage, docs-as-code without review gates.
- `..\..\architecture.md#deployment`: local PoC, no added frontend service.
- `..\..\architecture.md#repositories`: single `living-adr` repository.

## Desired State
A small, accessible HITL review UI renders pending `ReviewRequestPayload` instances from feature 015, presents feature 008 ADR drafts and evidence, validates reviewer actions, and resumes the paused LangGraph workflow with a `ReviewResumeCommand`. It creates no authoritative approval token and performs no graph write.

## Options Considered

### Option A — Server-rendered FastAPI/Jinja2 UI inside workflow-service (selected)
- **Pros:** Matches architecture, smallest PoC surface, easy to test with ASGI/template tests, accessible semantic HTML by default, direct access to workflow resume seam.
- **Cons:** Less interactive than SPA; styling must stay disciplined.
- **Fit:** Best fit for `#tech-stack`, `#deployment`, and M4 sequencing.

### Option B — Separate SPA frontend plus JSON API
- **Pros:** Rich interactivity and future multi-reviewer UX options.
- **Cons:** Adds build tooling, auth/session complexity, API surface, and accessibility burden before PoC validation; oversteps roadmap.
- **Decision:** Rejected for PoC.

### Option C — Command-line review action only
- **Pros:** Fastest implementation and minimal web risk.
- **Cons:** Fails feature brief requiring review surface; poor evidence ergonomics; weak accessibility for non-terminal users.
- **Decision:** Rejected.

### Option D — GitHub PR/check comment review only
- **Pros:** Meets developers where they work.
- **Cons:** Requires GitHub write/publish semantics and ties review UI to SCM; conflicts with local HITL seam and feature 011 publish-back boundaries.
- **Decision:** Rejected for 009; possible future integration.

## Selected Approach
Use FastAPI routes and Jinja2 templates in `workflow-service` with a thin `ReviewWorkflowGateway` around feature 015. The gateway fetches pending interrupt payloads and submits resume commands. Templates render draft/evidence/decision panels with semantic forms. Form handlers validate action-specific input, compute edited hashes for approve-after-edit, include reviewer identity from local config, and submit resume commands. All telemetry is metadata-only.

## Contract Bindings
- **Feature 008:** consume provisional draft content/hash/citations/model metadata; do not generate drafts or call Claude.
- **Feature 015:** render `ReviewRequestPayload` and submit `ReviewResumeCommand`; do not own graph assembly, checkpointer, replay, or routing.
- **Feature 010:** leave `approved_decision` absent/null from UI-only commands until 010 wraps or extends the resume path; do not persist approval events or mint capabilities.

## Module Surface
| Module / path | Purpose | Test focus |
|---|---|---|
| `src\living_adr\hitl\models.py` | UI view models, form DTOs, validation result values | Pure validation/model tests |
| `src\living_adr\hitl\gateway.py` | Thin adapter to feature 015 pending-review and resume services | Fake workflow gateway tests |
| `src\living_adr\hitl\auth.py` | Local UI token and signed form nonce helpers | Auth/nonce tests |
| `src\living_adr\hitl\hashing.py` | Edited draft hash helper compatible with 008/015 hashes | Deterministic hash tests |
| `src\living_adr\apps\workflow_service\hitl_routes.py` | FastAPI GET/POST routes and redirects | ASGI route tests |
| `src\living_adr\apps\workflow_service\templates\hitl\review.html` | Main accessible review template | Template semantics tests |
| `src\living_adr\apps\workflow_service\templates\hitl\status.html` | Submitted/not-found/unauthorized status states | Template state tests |
| `src\living_adr\apps\workflow_service\static\hitl.css` | Minimal accessible styling/focus/error states | Asset existence/snapshot tests |
| `tests\hitl\...` | Contract, route, validation, accessibility, and boundary tests | Prevent seam/boundary regressions |

## Anti-Patterns to Avoid
- UI-owned orchestration or checkpointer code.
- Approval capability minting or durable audit persistence in 009.
- Direct graph adapter/store writes or `ApprovalBoundMutationService` calls.
- Draft/evidence/comment bodies in logs, metrics, URLs, or default traces.
- SPA-only interactions or unlabeled controls.
- Treating model-generated draft text as authoritative.
- Re-fetching evidence from GitHub/Claude/graph internals instead of using payload/view model fields.

## Affected Repositories
| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add `hitl` package, workflow-service routes/templates/static assets, and tests binding to feature 015/008 contracts. | High |

## Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Feature 015 resume schema changes | Medium | High | Keep gateway isolated; contract tests assert current payload/command mapping. |
| Boundary with feature 010 blurs | Medium | High | Tests assert no capability minting, no audit durability, and no graph/mutation-service calls. |
| Reviewer fatigue/rubber-stamping | Medium | Medium | Evidence-first layout, confidence copy, visible alternatives/consequences, required reason for reject. |
| Accessibility gaps | Medium | High | Template tests for labels/headings/fieldsets/error associations; keyboard-focused acceptance criteria. |
| Sensitive draft/comment leakage | Medium | High | No body logging; metadata-only observability builder; POST bodies excluded from traces. |
| CSRF/replay form submission | Medium | Medium | Signed nonce tied to thread/draft hash/action window plus local UI token. |

## Decision
Proceed with Option A: accessible server-rendered FastAPI/Jinja2 UI inside `workflow-service`, integrated through feature 015's seam and consuming feature 008's provisional draft output, while preserving feature 010's authority/audit boundary.
