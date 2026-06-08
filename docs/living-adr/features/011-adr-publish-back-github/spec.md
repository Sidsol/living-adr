# Feature Specification: adr-publish-back-github

## Overview

Feature 011 publishes a human-approved `ADRRecord` back to the source GitHub repository when `RepositoryConfig.adr_publication_policy` requires GitHub publication. It is the final write-side step in the MVP ADR lifecycle: after feature 010 mints and validates an `ApprovedReviewDecision`, publish-back allocates an ADR number, renders the configured path such as `docs\adr\NNNN-<slug>.md`, commits the approved Markdown through feature 003's `GitHubProvider`/`SCMProvider` seam, records the `decision_id` on every audit and publication record, and remains idempotent for retries of the same approved decision.

The feature depends on feature 010 as the only authoritative-mutation path and feature 003 as the GitHub App provider seam. It does not redefine approval capability, GitHub ingestion, repository configuration, graph storage, or ADR drafting.

## User Stories

### [US-1] Publish approved ADR Markdown to GitHub — Priority: P1
**As an** architecture owner, **I want** approved ADRs committed to the configured repository path, **so that** the source repository contains durable docs-as-code rationale.

#### Acceptance Scenarios
- **Given** `adr_publication_policy` is `publish_to_github` or `publish_to_github_and_livingadr` and feature 010 provides a valid `ApprovedReviewDecision`, **When** publication runs, **Then** the approved `ADRRecord` Markdown is committed to the configured GitHub repository target branch through feature 003's GitHub provider.
- **Given** `adr_publication_policy` is `livingadr_only`, **When** the approved decision reaches publish-back, **Then** no GitHub commit occurs and an audit record states publication was skipped by policy.

### [US-2] Consume the approval-bound mutation path — Priority: P1
**As an** audit owner, **I want** publish-back authorized only through `ApprovalBoundMutationService`, **so that** no ADR file is published without the same human approval authority used for graph mutations.

#### Acceptance Scenarios
- **Given** publish-back is requested without an `ApprovedReviewDecision`, **When** the service validates authorization, **Then** no GitHub write occurs.
- **Given** the decision's repository, content hash, TTL, or target mutation fingerprint is invalid, **When** publication is attempted, **Then** feature 010 validation fails closed before calling GitHub.
- **Given** publication succeeds, **When** audit records are queried, **Then** the publication event joins to review, capability, and mutation records by `decision_id`.

### [US-3] Allocate deterministic ADR numbers and paths — Priority: P1
**As a** repository maintainer, **I want** published files named by repository policy, **so that** ADRs use stable, readable `NNNN-<slug>.md` numbering without conflicts.

#### Acceptance Scenarios
- **Given** existing ADR files are present under the configured path template, **When** a new approved ADR is published, **Then** the next number is one greater than the highest existing numeric prefix, zero-padded to four digits by default.
- **Given** the policy supplies a different directory, extension, padding width, or branch, **When** publication runs, **Then** the path is derived from `RepositoryConfig.adr_publication_policy` and related path/branch settings, not hardcoded.
- **Given** two different approved ADRs race for the same next number, **When** GitHub reports a conflict or branch head mismatch, **Then** the publisher refreshes listing/head state, reallocates if needed, and retries within configured limits before dead-lettering.

### [US-4] Guarantee idempotent re-publication — Priority: P1
**As a** platform operator, **I want** retries of the same approved decision to be safe, **so that** webhook replay or workflow retry cannot create duplicate ADR files or commits.

#### Acceptance Scenarios
- **Given** the same `decision_id` and same approved ADR content is retried after a successful commit, **When** publish-back runs, **Then** it returns the existing publication result without creating another file or commit.
- **Given** a file already exists carrying the same `decision_id` publication marker, **When** retry runs, **Then** it treats the operation as already complete.
- **Given** the same `decision_id` is used with a different content hash, target path, or repository, **When** validation runs, **Then** it fails as a target mutation mismatch.

### [US-5] Preserve provider swappability and security boundaries — Priority: P1
**As a** maintainer, **I want** GitHub-specific write details isolated in the SCM adapter, **so that** future Azure DevOps support and graph-store swapping are not blocked.

#### Acceptance Scenarios
- **Given** publish-back needs repository contents operations, **When** it calls SCM code, **Then** it uses provider port methods implemented by `GitHubProvider`, not raw GitHub REST calls from workflow/domain code.
- **Given** the MCP server or read-side query code imports publish modules, **When** boundary tests run, **Then** the dependency is absent or rejected because MCP remains read-only.

## Functional Requirements

- [FR-1] Consume feature 010 `ApprovedReviewDecision` through `ApprovalBoundMutationService` or a feature-010-approved publication wrapper; direct GitHub writes without that boundary are invalid.
- [FR-2] Record `decision_id` in publication intent, validation, commit success, skip, retry, dead-letter, and idempotent-return audit records.
- [FR-3] Use feature 003's `SCMProvider`/`GitHubProvider` and feature 002 `RepositoryConfig`; do not create a separate GitHub client or redefine provider credentials.
- [FR-4] Respect `RepositoryConfig.adr_publication_policy`: `livingadr_only`, `publish_to_github`, and `publish_to_github_and_livingadr`.
- [FR-5] Resolve target branch and path template from repository configuration; default to `docs\adr\NNNN-<slug>.md` on the configured ADR target branch or default branch.
- [FR-6] Slugify ADR titles deterministically using lowercase ASCII, hyphen separators, max 80 characters, and fallback `adr-<adr_record_id>` when title has no usable characters.
- [FR-7] Allocate ADR number by listing existing files matching the policy prefix pattern and choosing max existing number + 1; default initial number is `0001`.
- [FR-8] Store a durable publication record keyed by `decision_id`, repository, ADR record id, content hash, target branch, target path, and commit SHA.
- [FR-9] Make same-`decision_id` retries idempotent when repository/path/content hash/fingerprint match; reject mismatched retries.
- [FR-10] Detect existing same-decision publication markers in ADR front matter/comment metadata before creating a new file.
- [FR-11] Handle GitHub branch/file conflicts by bounded refresh-and-retry, then dead-letter with structured metadata.
- [FR-12] Emit metadata-only observability through the inherited `Observability` port; do not export raw ADR content by default.

## Non-Functional Requirements

- [NFR-1] Fail closed: any approval validation, audit persistence, GitHub permission, conflict-exhaustion, or config error prevents publication.
- [NFR-2] Testable without live GitHub by using fake `SCMProvider`, fake approval service, and project-local SQLite fixtures.
- [NFR-3] Preserve swappable-port philosophy: publication depends on SCM and approval ports, not adapter internals or LlamaIndex.
- [NFR-4] Commit messages and audit metadata must avoid raw diff/prompt/reviewer-comment leakage.
- [NFR-5] Publication must be repository-scoped and never infer target repo from ADR content alone.

## Scope

### In Scope
- GitHub ADR file publication for approved ADRs when repository policy enables it.
- ADR path rendering, slugging, numbering, conflict retry, idempotency, and publication audit records.
- Required SCM provider extensions for repository file listing/read/write if feature 003 has not already exposed them.
- Contract tests proving use of feature 010 and feature 003 seams.

### Out of Scope
- Drafting, editing, approving, rejecting, or regenerating ADR content.
- Redefining `ApprovedReviewDecision`, `ApprovalBoundMutationService`, `GitHubProvider`, or `RepositoryConfig`.
- Opening a GitHub pull request instead of committing directly for PoC; direct commit is the selected default.
- Azure DevOps implementation, multi-repo governance, branch protection bypass workarounds, or docs portal generation.
- MCP context serving or graph query behavior.

## Success Criteria

- [ ] Enabled publication policies commit approved ADR Markdown to the configured GitHub path and branch.
- [ ] Disabled policy skips GitHub writes with a linked audit record.
- [ ] Every publication attempt carries and records `decision_id` for audit linkage.
- [ ] Re-running the same approved decision returns the prior publication result without duplicate file or commit creation.
- [ ] ADR numbering starts at `0001`, advances from existing files, and resolves conflicts by refresh/retry.
- [ ] GitHub operations are performed only through feature 003 provider seams and repository configuration.
- [ ] Boundary tests prove publish-back cannot bypass feature 010 approval validation.

## Resolved Defaults / Open Questions

Autopilot resolves all planning questions for readiness:

- Publication mode default: direct commit to the configured target branch, not a PR. Rationale: feature-map explicitly leaves direct commit vs PR to this feature; direct commit is smaller for the single-user PoC after HITL approval.
- Path default: `docs\adr\NNNN-<slug>.md`; `NNNN` is four-digit zero-padded decimal.
- ADR number source: max numeric filename prefix in the configured ADR directory on the target branch.
- Idempotency marker: include `livingadr_decision_id: <decision_id>` in a machine-readable metadata block or HTML comment in the published ADR; use durable publication records as the primary idempotency store.
- Commit author: GitHub App identity; commit message `docs(adr): publish NNNN-<slug>` with `decision_id` in the body.
- Conflict retry default: three refresh-and-retry attempts before dead-letter.
