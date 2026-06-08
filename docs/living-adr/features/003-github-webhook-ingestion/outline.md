# Implementation Outline: github-webhook-ingestion

## Slice Strategy

The feature is decomposed into six vertical slices matching the feature-map estimate. The order follows the trust boundary first, then acceptance/idempotency, normalized contracts, evidence collection, replay/dead-letter recovery, and final observability/handoff hardening. Each slice is independently testable with fake config, fake persistence, and fake GitHub clients; no live GitHub or LangGraph production workflow is required.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| 1 | Verify GitHub webhook requests | US-1 | M | — | false | HITL | Security-critical raw-body HMAC boundary must be reviewed carefully. |
| 2 | Filter configured merged PR deliveries idempotently | US-2 | M | 1 | false | HITL | Defines durable idempotency and repository acceptance semantics. |
| 3 | Normalize SCMEvent and provider seam | US-3 | M | 2 | false | HITL | Establishes cross-feature contracts and Azure DevOps seam. |
| 4 | Fetch minimal PR/diff candidate evidence | US-4 | M | 3 | false | HITL | External API/rate-limit boundary and evidence/rationale separation need review. |
| 5 | Replay and dead-letter recovery | US-5 | M | 4 | false | HITL | Operational recovery can reprocess events and must preserve idempotency. |
| 6 | Observability and integration verification | US-1, US-5 | S | 5 | false | AFK | Additive metadata-only instrumentation and verification once behavior exists. |

## Slices

### Slice 1: Verify GitHub webhook requests

**Scope:** Add a thin workflow-service webhook handler/router and GitHub HMAC verifier that operates on raw request bytes before JSON parsing or side effects.

**User Stories:** US-1

**Automation:** HITL

**Automation Reason:** Security-critical raw-body HMAC boundary must be reviewed carefully.

**Deliverables:**

- `src\living_adr\scm\github_webhook.py` with signature verification and header parsing helpers.
- `src\living_adr\apps\workflow_service\webhooks.py` with a thin handler using the verifier.
- `tests\scm\test_github_webhook_signature.py` for valid, missing, malformed, and body-tamper cases.
- `tests\apps\test_github_webhook_endpoint.py` for endpoint rejection without downstream side effects.

**Checkpoint Criteria:**

- [ ] Valid `X-Hub-Signature-256` over raw bytes succeeds.
- [ ] Missing/malformed/incorrect signatures fail before JSON parsing or persistence.
- [ ] Handler requires provider delivery id and event name headers.
- [ ] Rejected requests produce metadata-only observability/error outcomes.

**Context Notes:**

- Key files: webhook helper, workflow-service webhook route, signature tests, endpoint tests.
- Dependencies: Feature 002 config/observability import conventions.
- Estimated complexity: Medium.

### Slice 2: Filter configured merged PR deliveries idempotently

**Scope:** Parse verified GitHub pull-request payloads, resolve repository identity against `RepositoryConfig`, filter to merged PR close events, and persist provider delivery states for idempotency.

**User Stories:** US-2

**Automation:** HITL

**Automation Reason:** Defines durable idempotency and repository acceptance semantics.

**Deliverables:**

- `src\living_adr\core\ingestion.py` with delivery-state models and outcome enums.
- `src\living_adr\persistence\ingestion_store.py` with delivery id lookup/upsert interface or initial SQLite-backed implementation.
- `src\living_adr\scm\github_webhook.py` extended with merged-PR payload extraction.
- Tests for configured repo acceptance, unconfigured repo rejection, non-merged PR skip, malformed payload failure, and duplicate delivery id behavior.

**Checkpoint Criteria:**

- [ ] Only `pull_request` `closed` + `merged=true` events for configured repositories are accepted.
- [ ] Duplicate `X-GitHub-Delivery` returns the prior outcome without duplicate event/evidence creation.
- [ ] Skipped/rejected deliveries persist structured metadata where safe.
- [ ] Repository matching uses `RepositoryIdentity`, not hardcoded PoC repo values.

**Context Notes:**

- Key files: core ingestion models, ingestion store, GitHub payload parser, tests.
- Dependencies: Slice 1 verifier and Feature 002 `RepositoryConfig`/`RepositoryIdentity`.
- Estimated complexity: Medium.

### Slice 3: Normalize SCMEvent and provider seam

**Scope:** Define provider-neutral `SCMEvent`, fetch handles, `SCMProvider` port, and GitHub normalizer so downstream workflow nodes do not traverse raw GitHub payloads.

**User Stories:** US-3

**Automation:** HITL

**Automation Reason:** Establishes cross-feature contracts and Azure DevOps seam.

**Deliverables:**

- `src\living_adr\core\scm.py` with `SCMEvent`, `SCMProvider`, PR metadata/file/diff value objects, and provider enums.
- `src\living_adr\scm\github_webhook.py` normalizer from accepted payload to `SCMEvent`.
- `tests\core\test_scm_event.py` and `tests\scm\test_github_event_normalization.py`.
- Export updates in `src\living_adr\core\__init__.py` if package style requires.

**Checkpoint Criteria:**

- [ ] `SCMEvent` includes repository, provider delivery id, normalized PR key, timestamps, PR number, refs, merge SHA, and fetch handles.
- [ ] Workflow-facing event model contains no required GitHub-only fields.
- [ ] `SCMProvider` methods accept `RepositoryIdentity` scope.
- [ ] Tests document how future Azure DevOps can map into the same normalized event shape.

**Context Notes:**

- Key files: core SCM contracts, GitHub normalizer, event tests.
- Dependencies: Slice 2 accepted delivery model.
- Estimated complexity: Medium.

### Slice 4: Fetch minimal PR/diff candidate evidence

**Scope:** Implement `GitHubProvider` methods behind `SCMProvider` using a fakeable client seam, then build/cache immutable candidate evidence for classifiers.

**User Stories:** US-4

**Automation:** HITL

**Automation Reason:** External API/rate-limit boundary and evidence/rationale separation need review.

**Deliverables:**

- `src\living_adr\scm\github_provider.py` with PR metadata, changed-files, and diff fetch methods.
- `src\living_adr\workflow\ingestion.py` with evidence builder from `SCMEvent` + provider responses.
- Persistence/cache additions for evidence records in `src\living_adr\persistence\ingestion_store.py`.
- `tests\scm\test_github_provider.py` and `tests\workflow\test_candidate_evidence.py` with fake GitHub client responses.

**Checkpoint Criteria:**

- [ ] Provider fetches only PR metadata, changed file metadata, and diff text/handle needed for V1.
- [ ] Evidence is repository-scoped, immutable, and linked to delivery id and normalized PR key.
- [ ] Repeated accepted delivery/replay can reuse cached evidence or avoid duplicate API calls.
- [ ] Provider errors are categorized for retry/dead-letter handling without emitting complete evidence.

**Context Notes:**

- Key files: GitHub provider, ingestion workflow/evidence builder, ingestion store, provider/evidence tests.
- Dependencies: Slice 3 `SCMProvider` and `SCMEvent` contracts.
- Estimated complexity: Medium.

### Slice 5: Replay and dead-letter recovery

**Scope:** Add replay service and dead-letter transitions for stored deliveries/events while preserving idempotency and safe evidence regeneration/reuse.

**User Stories:** US-5

**Automation:** HITL

**Automation Reason:** Operational recovery can reprocess events and must preserve idempotency.

**Deliverables:**

- `src\living_adr\workflow\replay.py` with replay orchestration over stored delivery/event records.
- Dead-letter and retry state transitions in `src\living_adr\core\ingestion.py` and persistence store.
- Optional CLI/function entry point such as `src\living_adr\apps\workflow_service\replay.py` if scaffold conventions support it.
- `tests\workflow\test_replay_dead_letter.py` covering retryable failure, poison event, replay of accepted event, and duplicate replay idempotency.

**Checkpoint Criteria:**

- [ ] Failed provider/normalization outcomes enter retryable or dead-letter state with error category and retry count.
- [ ] Replay uses stored delivery/event data and does not require a new GitHub webhook delivery.
- [ ] Replay cannot duplicate `SCMEvent` or complete evidence for the same normalized key.
- [ ] Dead-letter records retain enough metadata for operator diagnosis without raw secret/payload leakage.

**Context Notes:**

- Key files: replay service, core ingestion states, persistence store, replay tests.
- Dependencies: Slice 4 evidence collection and provider error classification.
- Estimated complexity: Medium.

### Slice 6: Observability and integration verification

**Scope:** Add metadata-only observability events/counters/spans across the full ingestion path and verify end-to-end behavior with fakes.

**User Stories:** US-1, US-5

**Automation:** AFK

**Automation Reason:** Additive metadata-only instrumentation and verification once behavior exists.

**Deliverables:**

- Observability calls in webhook handler, idempotency path, normalizer, evidence builder, replay/dead-letter paths.
- `tests\workflow\test_ingestion_observability.py` proving metadata contains allowed keys and excludes raw payload/diff content.
- `tests\workflow\test_github_webhook_ingestion_e2e.py` proving valid merged PR -> `SCMEvent` -> candidate evidence and duplicate delivery behavior with fakes.
- Verification commands documented/run through existing pytest/Ruff commands.

**Checkpoint Criteria:**

- [ ] Observability uses Feature 002 port and introduces no LangSmith dependency.
- [ ] Metadata excludes raw webhook bodies, raw diffs, secrets, prompts, drafts, and reviewer comments.
- [ ] End-to-end fake test covers HMAC -> idempotent delivery -> `SCMEvent` -> candidate evidence.
- [ ] Existing test and lint commands pass after implementation.

**Context Notes:**

- Key files: all ingestion modules plus observability/e2e tests.
- Dependencies: Slices 1-5 complete.
- Estimated complexity: Low.

## Slice Dependency Graph

```text
Slice 1 ──→ Slice 2 ──→ Slice 3 ──→ Slice 4 ──→ Slice 5 ──→ Slice 6
```

## Slice Dependency Graph (Machine-Readable)

```yaml
slices:
  - id: 1
    name: Verify GitHub webhook requests
    depends_on: []
    parallelizable: false
    automation: HITL
    automation_reason: "Security-critical raw-body HMAC boundary must be reviewed carefully."
    checkpoint_criteria_count: 4
  - id: 2
    name: Filter configured merged PR deliveries idempotently
    depends_on: [1]
    parallelizable: false
    automation: HITL
    automation_reason: "Defines durable idempotency and repository acceptance semantics."
    checkpoint_criteria_count: 4
  - id: 3
    name: Normalize SCMEvent and provider seam
    depends_on: [2]
    parallelizable: false
    automation: HITL
    automation_reason: "Establishes cross-feature contracts and Azure DevOps seam."
    checkpoint_criteria_count: 4
  - id: 4
    name: Fetch minimal PR/diff candidate evidence
    depends_on: [3]
    parallelizable: false
    automation: HITL
    automation_reason: "External API/rate-limit boundary and evidence/rationale separation need review."
    checkpoint_criteria_count: 4
  - id: 5
    name: Replay and dead-letter recovery
    depends_on: [4]
    parallelizable: false
    automation: HITL
    automation_reason: "Operational recovery can reprocess events and must preserve idempotency."
    checkpoint_criteria_count: 4
  - id: 6
    name: Observability and integration verification
    depends_on: [5]
    parallelizable: false
    automation: AFK
    automation_reason: "Additive metadata-only instrumentation and verification once behavior exists."
    checkpoint_criteria_count: 4
```

> **Note:** `parallelizable` is a static planning-time hint, not a runtime guarantee. `crispy-implement` re-evaluates parallelizability dynamically based on dependency satisfaction and file-set conflict detection at execution time.

## Context Management

- Maximum files open per slice: 5 implementation files plus matching tests for slices 1-4; 6 for replay/observability because they touch previous paths.
- Recommended context window reset points: after Slice 2 and after Slice 4.
- State that must carry across slices: `RepositoryIdentity` scope, provider delivery id as idempotency key, normalized PR key format, evidence-is-not-rationale rule, metadata-only observability rule, and no raw GitHub payload leakage beyond adapter boundaries.

## Verification Strategy

Run the repository's existing tests and lint after implementation: `uv run pytest` and `uv run ruff check` if available. Complete verification must include negative HMAC tests, duplicate-delivery tests, unconfigured/non-merged event tests, normalized `SCMEvent` contract tests, fake GitHub provider tests, replay/dead-letter tests, observability metadata hygiene tests, and one fake end-to-end valid merged PR ingestion path.
