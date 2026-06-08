# CRISPY Checklist: adr-publish-back-github

## Planning Completeness

- [ ] `spec.md` defines approval-bound publication, policy handling, idempotency, ADR numbering, and audit linkage.
- [ ] `research.md` binds explicitly to inherited project artifacts plus feature 010 and 003 dependency contracts.
- [ ] `intent.md` references `..\..\architecture.md#service-boundaries`, `#data-model`, `#tech-stack`, `#cross-cutting`, `#anti-patterns`, `#deployment`, and `#repositories`.
- [ ] `outline.md`, `plan.md`, `tasks.md`, and `implementation-manifest.yaml` all declare 5 slices.
- [ ] Task IDs are unique and consistently mapped to slices.

## Contract Gates

- [ ] Publish-back consumes feature 010 `ApprovedReviewDecision` via `ApprovalBoundMutationService`; no direct publication by `decision_id` string alone.
- [ ] Every publication record and commit audit includes `decision_id` for review/mutation linkage.
- [ ] GitHub writes use feature 003 `SCMProvider`/`GitHubProvider`; no parallel GitHub client or credential path is introduced.
- [ ] Target branch/path comes from `RepositoryConfig.adr_publication_policy` and related publication settings.
- [ ] MCP/read-side context server remains unable to publish or mutate.

## Quality Gates for Future Implementation

- [ ] `livingadr_only` policy skips GitHub writes and records a decision-linked audit event.
- [ ] `publish_to_github` and `publish_to_github_and_livingadr` policies commit approved Markdown to the configured path.
- [ ] Replaying the same `decision_id` and fingerprint returns the prior result without duplicate files or commits.
- [ ] Reusing the same `decision_id` with a different repository, path, branch, or content hash is rejected.
- [ ] ADR numbering starts at `0001`, uses max existing numeric prefix + 1, and handles conflict refresh/retry.
- [ ] Existing same-decision file markers are detected for recovery.
- [ ] GitHub permission/branch/conflict failures fail closed and dead-letter with metadata only.
- [ ] Tests use fakes/project-local SQLite and no live GitHub, Claude, LangSmith, browser, or external graph database.

## Anti-Pattern Checks

- [ ] No direct GitHub REST calls from workflow/domain publication code.
- [ ] No publication before feature 010 approval validation.
- [ ] No hardcoded `docs\adr` path when repository config supplies a template.
- [ ] No duplicate ADR files for one approved decision.
- [ ] No raw ADR body, PR diff, prompt, or reviewer comment in default observability.
- [ ] No PR publication flow silently added to PoC direct-commit default.

## Readiness Decision

- [ ] Manifest has `ready: true`.
- [ ] Open questions are resolved with documented defaults.
- [ ] No production/application code is created by this planning run.
