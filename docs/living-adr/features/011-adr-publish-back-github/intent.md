# Architecture Intent: adr-publish-back-github

## Current State

LivingADR has a planned approval capability (feature 010) and GitHub App provider seam (feature 003). The project architecture already states that when `RepositoryConfig.adr_publication_policy` includes GitHub publication, an approved ADR triggers a downstream publish step to `docs/adr/NNNN-<slug>.md` by default. Feature 011 is the missing publication implementation plan.

Relevant architecture anchors:

- `..\..\architecture.md#service-boundaries`: `workflow-service` owns approved publication workflow; `ApprovalBoundMutationService` is the only authoritative write path; MCP remains read-only.
- `..\..\architecture.md#data-model`: `RepositoryConfig`, `ApprovedReviewDecision`, `ADRRecord`, and `AuditEvent` carry repository scope, publication policy, path template, content hash, and `decision_id`.
- `..\..\architecture.md#tech-stack`: Python 3.12, FastAPI workflow-service, SQLite state/audit, GitHub App provider via httpx/PyJWT, pytest/Ruff.
- `..\..\architecture.md#cross-cutting`: fail-closed validation, GitHub App least privilege, metadata-only observability, source-of-truth discipline.
- `..\..\architecture.md#anti-patterns`: avoid excessive agency, prompt/tool injection, event duplication, docs-as-code without review gates, and cross-SCM abstraction leaks.
- `..\..\architecture.md#deployment`: PoC same-host workflow-service writer with SQLite/WAL and replay/dead-letter state.
- `..\..\architecture.md#repositories`: single implementation repository `living-adr`.

## Desired State

Feature 011 provides a repository-scoped ADR publication service that commits approved ADR Markdown to GitHub only when policy enables it, only through feature 010 authorization, and only through feature 003 provider seams. Each publication has durable audit and idempotency records linked by `decision_id`; retries cannot create duplicate ADR files; ADR numbering follows repository policy and resolves conflicts safely.

## Options Considered

### Option A — Publish directly from workflow node with raw GitHub REST

**Approach:** After approval, a workflow node calls GitHub REST to create `docs\adr\NNNN-<slug>.md`.

- Pros: Smallest code path.
- Cons: Bypasses SCM port, couples workflow to GitHub, weak Azure DevOps seam, easy to bypass feature 010, poor testability.
- Decision: Rejected.

### Option B — Open a pull request for every approved ADR

**Approach:** Create a branch and PR containing the ADR; rely on GitHub PR review/merge for publication.

- Pros: Familiar docs-as-code review loop; branch protection friendly.
- Cons: Duplicates HITL review for the single-user PoC, delays M4 end-to-end outcome, adds branch lifecycle/notification scope, and complicates idempotency.
- Decision: Rejected for PoC; viable post-PoC policy extension.

### Option C — Store only in LivingADR graph, skip repository publication

**Approach:** Treat graph/ADR repository as the only source of approved rationale and never write Markdown back to source repo.

- Pros: Avoids GitHub write permissions and numbering conflicts.
- Cons: Fails feature 011 scope, weakens docs-as-code visibility, and does not satisfy publication policies requiring source-repo ADRs.
- Decision: Rejected.

### Option D — Approval-bound publication service using SCM provider direct commit (selected)

**Approach:** Add a domain/workflow-service publication component. It derives target path from `RepositoryConfig`, validates/consumes an `ApprovedReviewDecision` through feature 010, lists existing ADR files and allocates `NNNN`, commits via `SCMProvider`/`GitHubProvider`, stores publication records, and handles idempotent retry/conflict refresh.

- Pros: Aligns with architecture, preserves swappable ports, satisfies PoC, supports audit linkage, and keeps future PR/Azure DevOps modes additive.
- Cons: Requires careful transaction boundaries across local audit and remote GitHub commit.
- Decision: Selected.

## Selected Approach

Implement Option D. The implementation should introduce a publication package owned by `workflow-service` and backed by SQLite audit/idempotency tables. The service will not own approval capability semantics or GitHub credentials; it consumes feature 010 and feature 003 contracts.

High-level flow:

1. Receive approved ADR publication request from feature 015/010 handoff.
2. Load `RepositoryConfig` for `RepositoryIdentity` and evaluate `adr_publication_policy`.
3. Build canonical publication target fingerprint: repository, ADR record id, approved content hash, policy, target branch, path template, and decision id.
4. Ask feature 010 `ApprovalBoundMutationService` or its publication-authorizing wrapper to validate/consume the `ApprovedReviewDecision` for that fingerprint.
5. If policy skips GitHub, persist a skipped publication audit linked by `decision_id`.
6. If enabled, use feature 003 SCM provider to list ADR files, allocate number/path, check existing same-decision marker, and commit approved Markdown.
7. Persist success with target path and commit SHA; return prior result for same-decision retries.

## Module Surface Analysis

| Module / Path | Purpose | Test Focus |
|---|---|---|
| `src\living_adr\publication\models.py` | `ADRPublicationRequest`, `ADRPublicationTarget`, `ADRPublicationResult`, status/error DTOs | Pure serialization and fingerprint tests |
| `src\living_adr\publication\slugging.py` | Deterministic title slug and path rendering helpers | Unicode, empty-title, max-length, path-template tests |
| `src\living_adr\publication\numbering.py` | Existing ADR filename scan and next-number allocation | Gap/highest-number/conflict tests |
| `src\living_adr\publication\repository.py` | SQLite publication record/idempotency repository | Durable same-decision retry tests |
| `src\living_adr\publication\service.py` | Approval-bound publish orchestration and policy handling | No provider call without authorization; policy skip; success path |
| `src\living_adr\scm\provider_contracts.py` or existing `core\scm.py` | Provider-neutral contents operations if absent | Fake provider conformance tests |
| `src\living_adr\scm\github_provider.py` | GitHub App contents implementation behind existing provider | HTTP fake tests; no live GitHub |
| `src\living_adr\workflow\publication_node.py` | Feature 015 handoff node for approved ADRs | Workflow integration tests |
| `tests\publication\...` | Unit/integration tests for publish-back | Idempotency, numbering, audit, boundary coverage |

## Anti-Patterns to Avoid

- Direct GitHub REST calls outside feature 003 `GitHubProvider`.
- Publishing with only a `decision_id` string instead of a validated `ApprovedReviewDecision`.
- Allocating ADR numbers from local stale state only without target-branch refresh/conflict handling.
- Creating a second ADR file on retry of the same approved decision.
- Treating `livingadr_only` as an error; it is a policy skip with audit linkage.
- Adding publish capability to MCP or any read-side context server module.
- Logging raw ADR body, PR diff, prompt, or reviewer comment in observability.
- Hardcoding `docs\adr` when policy supplies a different path template.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add publication domain package, SCM contents-port extensions, workflow publication handoff, SQLite publication records, and tests. | High |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Duplicate files on replay | Medium | High | Durable publication record keyed by `decision_id`; embedded marker detection; idempotent same-fingerprint return. |
| Number conflict on concurrent approvals | Medium | Medium | Fetch current target branch listing, retry on conflict up to three times, then dead-letter. |
| Branch protection blocks direct commit | Medium | Medium | Fail closed with typed provider error; document PR mode as post-PoC policy extension. |
| Approval TTL expires before remote commit | Low | High | Validate at mutation start through feature 010; avoid long pre-validation work; retry requires fresh approval if expired. |
| GitHub permission missing | Medium | Medium | Startup/onboarding should validate `contents:write` for publish policies; publication dead-letters with clear metadata. |
| Port abstraction too GitHub-specific | Medium | High | Name SCM operations around repository files/commits and keep provider metadata opaque. |
| Audit and remote commit not atomic | Medium | High | Reserve publication intent before call; finalize success/failure after call; idempotency marker allows recovery if local finalize fails after remote success. |

## Decision

Use an approval-bound direct-commit publication service for PoC. Bind every GitHub write to feature 010 `ApprovedReviewDecision` validation and every GitHub operation to feature 003 provider seams. Resolve PR-based publication, branch-protection workflows, and Azure DevOps write-back as post-PoC extensions.
