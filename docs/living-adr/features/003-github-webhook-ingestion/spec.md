# Feature Specification: github-webhook-ingestion

## Overview

Feature 003 establishes the GitHub-first webhook ingestion boundary for LivingADR. It receives GitHub App webhook deliveries for merged pull requests, verifies HMAC signatures, deduplicates by provider delivery id, normalizes accepted deliveries into repository-scoped `SCMEvent` records, exposes minimal PR/diff fetch handles through the `SCMProvider`/`GitHubProvider` adapter seam, records replay/dead-letter state, and emits candidate evidence for downstream structural-change classifiers.

This feature consumes Feature 002's `RepositoryConfig`, `RepositoryIdentity`, and no-op `Observability` port. It serves TH-01 Change Ingestion & Event Triggering and unlocks features 004, 005, 014, 015, and 011. It is GitHub-first for the PoC while preserving an Azure DevOps adapter seam through provider-neutral core event concepts.

## Canonical Terms

| Term | Meaning |
|---|---|
| `SCMEvent` | Provider-neutral, repository-scoped event envelope for accepted merged-PR events and future SCM events. |
| Provider delivery id | GitHub `X-GitHub-Delivery` value; persisted as the primary idempotency key. |
| Normalized PR key | Repository-scoped provider-neutral pull-request identifier such as provider + repo + PR number + merge commit SHA. |
| Candidate evidence | Immutable PR/diff metadata and lightweight summaries emitted for classifiers; it is evidence, not approved rationale. |
| Dead-letter event | Delivery that cannot proceed after validation/parsing/fetch failures and is retained with error metadata for operator inspection or replay. |
| Replay | Manual or automated reprocessing of a stored delivery/evidence record without requiring GitHub to resend the webhook. |
| `SCMProvider` | Core provider-neutral port for fetching pull request metadata, changed files, and diff text/handles. |
| `GitHubProvider` | GitHub App adapter implementing `SCMProvider`; it owns GitHub API details and permissions. |

## User Stories

### [US-1] Verify GitHub webhook authenticity — Priority: P1

**As a** LivingADR operator, **I want** webhook requests verified with the configured GitHub webhook secret, **so that** repository events cannot be spoofed before they enter the workflow.

#### Acceptance Scenarios

- **Given** a GitHub webhook request with a valid `X-Hub-Signature-256`, delivery id, event name, and JSON payload, **When** the workflow-service webhook endpoint receives it, **Then** signature verification succeeds before payload processing.
- **Given** the signature is missing, malformed, or does not match the raw request body, **When** the endpoint receives the request, **Then** it rejects the delivery without creating an `SCMEvent`, evidence record, or SCM API call.
- **Given** a rejected request, **When** observability is invoked, **Then** only metadata such as event name, delivery id presence, repository key if known, and error type is emitted.

### [US-2] Accept only configured merged PR events idempotently — Priority: P1

**As a** downstream workflow author, **I want** only merged pull-request events from configured repositories to become ingestion records, **so that** classifiers receive relevant, repository-scoped events without duplicate processing.

#### Acceptance Scenarios

- **Given** a valid GitHub `pull_request` webhook where `action=closed` and `pull_request.merged=true` for a configured repository, **When** ingestion runs, **Then** it stores one accepted delivery and creates one normalized event candidate.
- **Given** the same `X-GitHub-Delivery` is received again, **When** ingestion runs, **Then** processing is idempotent and returns the prior delivery state without duplicating `SCMEvent` or candidate evidence.
- **Given** a valid webhook for an unconfigured repository, non-PR event, unmerged closed PR, opened/synchronized PR, or deleted/malformed PR payload, **When** ingestion runs, **Then** it records a skipped or rejected metadata outcome according to the error category and emits no classifier candidate.

### [US-3] Normalize merged PRs into provider-neutral SCMEvent records — Priority: P1

**As a** LangGraph workflow implementer, **I want** a stable `SCMEvent` model that hides GitHub-specific taxonomy, **so that** downstream workflow nodes and future Azure DevOps support do not depend on raw GitHub payloads.

#### Acceptance Scenarios

- **Given** an accepted merged PR delivery, **When** the normalizer runs, **Then** the resulting `SCMEvent` includes `RepositoryIdentity`, provider, provider event type, provider delivery id, normalized PR key, PR number, source/base refs, merge commit SHA when present, sender metadata, delivery timestamp, and fetch handles.
- **Given** a downstream consumer receives an `SCMEvent`, **When** it needs PR details or diff content, **Then** it uses `SCMProvider` fetch methods with `RepositoryIdentity` and event handles rather than raw GitHub payload traversal.
- **Given** Azure DevOps is implemented later, **When** its adapter maps service hooks into ingestion, **Then** workflow-facing fields remain normalized and provider-specific fields remain inside the adapter/event metadata boundary.

### [US-4] Fetch minimal PR/diff evidence for classifiers — Priority: P1

**As a** structural-change classifier, **I want** cached minimal PR metadata, changed file metadata, and diff handles/summaries, **so that** dependency/schema/API detection can classify changes without broad repository mining.

#### Acceptance Scenarios

- **Given** an accepted `SCMEvent`, **When** evidence collection runs, **Then** `GitHubProvider` fetches only the PR metadata, changed file list, and diff text or diff handle required for V1 classifier input.
- **Given** GitHub returns rate-limit, permission, missing-resource, or transient errors, **When** evidence collection handles the failure, **Then** the delivery enters retryable or dead-letter state with structured error metadata and no partial classifier candidate is emitted as complete.
- **Given** evidence is collected successfully, **When** downstream features consume it, **Then** they receive immutable candidate evidence scoped to the same `RepositoryIdentity`, linked to provider delivery id and normalized PR key.

### [US-5] Support replay, dead-letter handling, and observability — Priority: P1

**As a** platform operator, **I want** ingestion outcomes to be replayable and observable, **so that** webhook gaps, duplicate deliveries, and poison events can be diagnosed without losing candidate changes.

#### Acceptance Scenarios

- **Given** a delivery is accepted, skipped, failed, or dead-lettered, **When** ingestion completes, **Then** its state, delivery id, repository scope if known, normalized PR key if known, retry count, and error category are persisted.
- **Given** an operator replays a stored delivery or accepted event, **When** replay runs, **Then** idempotency is preserved and evidence is regenerated or reused according to the same normalized keys.
- **Given** any ingestion path runs, **When** `Observability` records events/counters/spans, **Then** it uses Feature 002's port and excludes raw diffs, full webhook bodies, secrets, and reviewer/model content from metadata.

## Functional Requirements

- [FR-1] Add a workflow-service GitHub webhook endpoint or handler that operates on raw request bytes for signature verification.
- [FR-2] Verify `X-Hub-Signature-256` using the configured webhook secret before JSON parsing or side effects.
- [FR-3] Require and persist GitHub `X-GitHub-Delivery` as the provider delivery id for idempotency.
- [FR-4] Filter to GitHub `pull_request` events where `action=closed` and `pull_request.merged=true`.
- [FR-5] Resolve payload repository identity against Feature 002 `RepositoryConfig`; unconfigured repositories must not enter classifier flow.
- [FR-6] Store delivery processing state with accepted, skipped, failed, replayed, and dead-letter outcomes.
- [FR-7] Define `SCMEvent` in core with repository scope, provider delivery identity, normalized event fields, timestamps, and fetch handles.
- [FR-8] Define `SCMProvider` port methods for minimal PR metadata, changed file metadata, and diff/diff-handle retrieval.
- [FR-9] Implement `GitHubProvider` behind `SCMProvider` without leaking GitHub-only payload traversal into workflow nodes.
- [FR-10] Emit immutable candidate evidence linked to `SCMEvent`, provider delivery id, normalized PR key, and fetch provenance.
- [FR-11] Cache or persist fetched PR/diff evidence enough to avoid duplicate API calls on idempotent retries/replay.
- [FR-12] Classify GitHub API failures into retryable, skipped, or dead-letter categories with structured error metadata.
- [FR-13] Expose a manual replay entry point that reprocesses stored delivery/event records without bypassing HMAC-origin audit or idempotency checks.
- [FR-14] Instrument verification, idempotency, normalization, fetch, replay, and dead-letter outcomes through the inherited `Observability` port.
- [FR-15] Preserve Azure DevOps as a future adapter by keeping provider-specific taxonomies, permissions, and payload fields inside SCM adapters.

## Non-Functional Requirements

- [NFR-1] Security: invalid HMAC deliveries are rejected before JSON parsing, persistence side effects, classifier dispatch, or SCM API calls.
- [NFR-2] Idempotency: duplicate provider delivery ids produce deterministic prior outcomes and never duplicate `SCMEvent` or complete evidence records.
- [NFR-3] Minimal GitHub access: fetch only merged-PR evidence required for V1 classifiers; no broad history backfill in this feature.
- [NFR-4] Testability: HMAC verification, filtering, idempotency, normalization, provider seam, replay, dead-letter, and observability behavior are unit/integration-testable without live GitHub.
- [NFR-5] Extensibility: GitHub-specific fields remain in adapter metadata so Azure DevOps can map service hooks into the normalized model later.
- [NFR-6] Trace hygiene: observability metadata excludes raw webhook bodies, raw diffs, secrets, prompts, drafts, and reviewer comments.

## Scope

### In Scope

- GitHub App webhook verification and merged-PR filtering.
- Delivery-id idempotency and delivery state persistence design.
- Core `SCMEvent`, `SCMProvider`, and `ChangeEvidence`/candidate evidence intake contracts needed by downstream classifiers.
- GitHub provider adapter methods for minimal PR metadata, changed files, and diff retrieval.
- Replay/dead-letter state and operator-facing replay entry point.
- Observability calls through Feature 002's no-op-compatible port.

### Out of Scope

- Dependency, schema, or API-contract classification logic; features 004 and 005 own classifiers.
- ADR drafting, Claude calls, HITL review, graph mutation, MCP query, and publish-back beyond passing fetch handles needed by feature 011.
- Azure DevOps implementation; only the seam is preserved.
- Webhook secret storage implementation beyond consuming environment/vault-configured secret references.
- Broad backfill, historical repository mining, or scheduled polling.
- Production LangGraph checkpointing beyond handing off accepted normalized events; feature 015 owns orchestration durability.

## Themes, Metrics, and Failure Modes Served

- **Theme:** TH-01 Change Ingestion & Event Triggering.
- **MVP support:** M2 core foundation for GitHub-first PoC; downstream event source for structural classifiers, workflow checkpointing, onboarding diagnostics, and publish-back GitHub access.
- **Success metrics:** Directly supports SM-02 by timestamping PR merge ingestion and draft-start evidence availability; supports SM-05 indirectly by preserving source-of-truth evidence before approval-bound mutations; supports SM-01 by reducing noise before draft generation.
- **Failure modes addressed:** FM-17 webhook replay complexity, FM-18 rate-limit starvation, FM-24 cross-SCM abstraction leaks, plus FM-14 prompt/tool injection and FM-21 trace leakage through untrusted payload and observability controls.

## Dependencies

- **Project artifacts:** `..\..\architecture.md`, `..\..\domain-research.md`, `..\..\vision.md`, `..\..\feature-map.md`, `..\..\roadmap.md`.
- **Feature dependency:** 002 `tracked-repository-configuration` provides `RepositoryConfig`, `RepositoryIdentity`, startup config loading, and `Observability` / `NoOpObservability`.
- **Downstream consumers:** 004, 005, 011, 014, 015 and later 008/009/010 through workflow handoff.
- **Tech stack assumptions:** Python 3.12, FastAPI workflow-service, Pydantic/domain models, pytest, httpx or GitHub REST client behind adapter, SQLite WAL/outbox persistence, uv, Ruff.

## Success Criteria

- [ ] Valid GitHub merged-PR webhook deliveries are HMAC-verified before payload processing.
- [ ] Duplicate GitHub delivery ids are idempotent and do not duplicate events/evidence.
- [ ] Accepted deliveries produce normalized repository-scoped `SCMEvent` records.
- [ ] Minimal PR metadata, changed file metadata, and diff handles are fetched through `SCMProvider`/`GitHubProvider`.
- [ ] Candidate evidence is immutable, linked to delivery id and normalized PR key, and ready for classifiers.
- [ ] Replay and dead-letter states are persisted and test-covered.
- [ ] Azure DevOps remains a future adapter without GitHub-specific workflow leakage.
- [ ] Observability uses the inherited port and metadata-only trace discipline.

## Open Questions

- Exact local PoC webhook delivery path remains open at project level (tunnel, relay, hosted endpoint, or manual fixture), but implementation can target a FastAPI handler plus replay CLI/function.
- Exact GitHub App permission set should be finalized during onboarding; this feature assumes minimum pull request and contents/read metadata sufficient for PR files/diffs.
