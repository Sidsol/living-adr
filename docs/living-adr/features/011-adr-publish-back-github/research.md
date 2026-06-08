# Research: adr-publish-back-github

## Research Scope

This blind feature analysis grounds feature 011 in inherited project artifacts and dependency contracts. No production code was inspected or changed. The goal is to plan how approved LivingADR records become repository-resident docs-as-code artifacts without bypassing approval, audit, GitHub provider, or configuration seams.

## Inherited Project Findings

- `..\..\vision.md` defines LivingADR as an automated architecture archivist that preserves human-approved rationale and makes it queryable. Feature 011 serves the preservation half by placing approved ADRs in the source repository.
- `..\..\domain-research.md` identifies Nygard ADRs, MADR, adr-tools, Log4brains, Backstage TechDocs, GitHub Apps, docs-as-code, webhook idempotency, and auditability as relevant prior art. File numbering and repository storage are common ADR lifecycle patterns, while docs-as-code without review gates is a known failure mode.
- `..\..\architecture.md#service-boundaries` assigns approved publication workflow to `workflow-service`, keeps MCP read-only, and states `ApprovalBoundMutationService` is the only authorized write path.
- `..\..\architecture.md#data-model` defines `RepositoryConfig.adr_publication_policy` with ADR publication policy, target branch, and default `docs/adr/NNNN-<slug>.md`; `ApprovedReviewDecision` includes `decision_id`, content hash, TTL, target mutation fingerprint, and repository scope.
- `..\..\architecture.md#cross-cutting` requires fail-closed approval-bound mutation, transactional audit events, metadata-only observability, and GitHub App `contents:write` only when publication policy needs it.
- `..\..\feature-map.md` lists feature 011 as P1, ~5 slices, dependent on 010 and 003, non-parallelizable, and the final serial publish-back feature in W6.
- `..\..\roadmap.md` places 011 in M4, completing the first end-to-end approved ADR path with draft, review, durable approval, GitHub publication, graph projection, and MCP context delivery.

## Dependency Contract Bindings

### Feature 010 — approval-capability-and-audit-durability

Feature 010 is authoritative for `ApprovedReviewDecision` and `ApprovalBoundMutationService`. Feature 011 must:

- Accept only approved decisions minted by feature 010.
- Pass the decision and canonical target mutation fingerprint through feature 010 validation before any GitHub write.
- Preserve one-shot/idempotent retry semantics: same `decision_id` and same target fingerprint may return prior result; different target is rejected.
- Reuse feature 010 errors such as `DecisionExpiredError`, `DecisionAlreadyConsumedError`, `DraftContentMismatchError`, and `TargetMutationMismatchError` rather than inventing parallel errors.
- Record publication audit rows linked by `decision_id` so SM-05 can prove no authoritative mutation happened without approval.

### Feature 003 — github-webhook-ingestion

Feature 003 owns `SCMProvider`, `GitHubProvider`, provider credentials, repository scoping, and GitHub API isolation. Feature 011 must:

- Extend or consume the existing SCM port for contents operations: list files, read file by path/ref, create/update file/commit, get target branch head.
- Keep raw GitHub REST details inside `GitHubProvider`; workflow/domain code should call provider-neutral methods with `RepositoryIdentity` and config-derived targets.
- Use feature 002/003 `RepositoryConfig` and `RepositoryIdentity` rather than deriving repository or branch from ADR content.
- Preserve future Azure DevOps extensibility by naming operations semantically, e.g., `publish_repository_file(...)`, not `put_github_contents(...)`.

## Domain Analysis

ADR publish-back is a docs-as-code lifecycle action. Existing ADR tooling normally creates numbered Markdown files in `doc/adr` or `docs/adr`, scans existing numeric prefixes, and writes the next number. In an automated multi-step workflow, the risky parts are not Markdown rendering itself; they are authority, idempotency, concurrency, and target correctness.

Key domain concepts for feature 011:

| Term | Meaning |
|---|---|
| Publication policy | Repository config value deciding whether approved ADRs remain internal only or are committed to GitHub. |
| ADR path template | Configured pattern for directory, numeric prefix, slug, and extension; default `docs\adr\NNNN-<slug>.md`. |
| ADR number allocation | Selecting the next numeric prefix by inspecting target-branch ADR files and resolving conflicts. |
| Publication record | Durable local record keyed by `decision_id` and target fingerprint that captures path, branch, commit SHA, and status. |
| Idempotency marker | Decision-linked metadata embedded in the published file so external repository state can be recognized on retry/recovery. |
| Direct commit | Selected PoC default after HITL approval; avoids a second review loop in a single-user PoC. |

## Failure Modes and Mitigations

| Failure mode | Risk | Planning mitigation |
|---|---|---|
| Publish bypasses approval | Unapproved authoritative docs change | Require feature 010 service validation before provider call; boundary tests. |
| Duplicate ADR on retry | Multiple files for one decision | Publication table keyed by `decision_id`; embedded marker scan; same-fingerprint idempotent return. |
| Number collision | Concurrent decisions choose same `NNNN` | Refresh directory/head on conflict; bounded retry; unique target fingerprint. |
| Wrong repo/branch | ADR published to unintended source | All calls require `RepositoryIdentity`; branch/path from `RepositoryConfig`. |
| GitHub adapter coupling | Future SCM support blocked | Use provider port methods; keep REST details inside adapter. |
| Docs-as-code without review | Generated Markdown treated as accepted rationale | Consume only feature 010 approved decisions; include content hash validation. |
| Trace leakage | Raw ADR or diff leaves default-deny boundary | Metadata-only observability; raw content excluded by default. |
| Branch protection rejects direct commit | PoC publication fails | Fail closed and dead-letter; PR mode remains post-PoC extension. |

## Research Conclusions

Feature 011 should be a thin, approval-bound publication service, not a new workflow authority. The selected shape is: validate policy and config, ask feature 010 to authorize/consume a publication fingerprint, allocate path/number through SCM provider reads, commit through `GitHubProvider`, persist a decision-linked publication record, and make all retries converge on the same result. This matches docs-as-code prior art while avoiding the architecture anti-patterns of excessive agency, cross-SCM leakage, and generated docs without review gates.
