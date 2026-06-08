# Implementation Plan: github-webhook-ingestion

## Technical Context

- Language/Framework: Python 3.12, FastAPI workflow-service webhook endpoint/handler, provider-adapter modules.
- Key Dependencies: Feature 002 `RepositoryIdentity`, `RepositoryConfig`, `LivingADRConfig`, `Observability`; standard `hmac`/`hashlib`; GitHub REST client seam using existing HTTP dependency if scaffolded.
- Test Framework: pytest with fake GitHub client, fake config, fake observability, and local SQLite/store fixtures.
- Build System: uv with `pyproject.toml`; lint/format via Ruff.
- Architecture anchors: `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#anti-patterns`.

## Project Structure

```text
living-adr\
├── pyproject.toml                                      ← MODIFY only if an HTTP/GitHub client dependency is missing
├── src\living_adr\
│   ├── core\
│   │   ├── __init__.py                                 ← MODIFY: export stable SCM/ingestion contracts if convention requires
│   │   ├── scm.py                                      ← CREATE: SCMEvent, SCMProvider, PR/diff/evidence contracts
│   │   └── ingestion.py                                ← CREATE: delivery state, outcomes, error categories
│   ├── scm\
│   │   ├── __init__.py                                 ← CREATE/MODIFY: adapter exports
│   │   ├── github_webhook.py                           ← CREATE: HMAC, header parsing, payload filtering, normalization
│   │   └── github_provider.py                          ← CREATE: GitHubProvider fakeable API adapter
│   ├── persistence\
│   │   ├── __init__.py                                 ← CREATE/MODIFY if package exists
│   │   └── ingestion_store.py                          ← CREATE: delivery/evidence idempotency store
│   ├── workflow\
│   │   ├── ingestion.py                                ← CREATE: evidence builder and workflow handoff
│   │   └── replay.py                                   ← CREATE: replay/dead-letter recovery service
│   └── apps\workflow_service\
│       ├── webhooks.py                                 ← CREATE: webhook route/handler
│       └── replay.py                                   ← CREATE optional: operator replay entry point if app conventions support
└── tests\
    ├── apps\test_github_webhook_endpoint.py            ← CREATE
    ├── core\test_scm_event.py                          ← CREATE
    ├── scm\test_github_webhook_signature.py            ← CREATE
    ├── scm\test_github_event_filtering.py              ← CREATE
    ├── scm\test_github_event_normalization.py          ← CREATE
    ├── scm\test_github_provider.py                     ← CREATE
    ├── workflow\test_ingestion_idempotency.py          ← CREATE
    ├── workflow\test_candidate_evidence.py             ← CREATE
    ├── workflow\test_replay_dead_letter.py             ← CREATE
    ├── workflow\test_ingestion_observability.py        ← CREATE
    └── workflow\test_github_webhook_ingestion_e2e.py   ← CREATE
```

## Implementation Phases

### Phase 1: Verify GitHub webhook requests

#### Step 1.1: Add HMAC verifier tests (RED)

- **Task ID:** TASK-001
- **File:** `tests\scm\test_github_webhook_signature.py`
- **Action:** Create
- **Changes:** Test valid `sha256=` signature over raw bytes, body tampering, missing signature, unsupported algorithm, malformed hex, missing delivery id, and missing event name.

#### Step 1.2: Implement GitHub webhook verifier (GREEN)

- **Task ID:** TASK-002
- **File:** `src\living_adr\scm\github_webhook.py`
- **Action:** Create
- **Changes:** Add raw-byte HMAC verification using constant-time comparison, header extraction result type, and typed exceptions/outcomes for missing or invalid headers.

#### Step 1.3: Add workflow endpoint rejection tests (RED)

- **Task ID:** TASK-003
- **File:** `tests\apps\test_github_webhook_endpoint.py`
- **Action:** Create
- **Changes:** Test that invalid signatures return rejection and do not call fake store, provider, or normalizer; valid signed body reaches the next handler seam.

#### Step 1.4: Implement thin webhook handler/route (GREEN)

- **Task ID:** TASK-004
- **File:** `src\living_adr\apps\workflow_service\webhooks.py`
- **Action:** Create
- **Changes:** Add FastAPI-compatible handler accepting raw body and headers, invoking verifier before JSON parsing, injecting config/store/provider/observability dependencies, and returning safe metadata responses.

### Phase 2: Filter configured merged PR deliveries idempotently

#### Step 2.1: Add delivery-state tests (RED)

- **Task ID:** TASK-005
- **File:** `tests\workflow\test_ingestion_idempotency.py`
- **Action:** Create
- **Changes:** Test first delivery insert, exact duplicate delivery returning prior result, conflicting duplicate metadata behavior, and safe skipped/rejected states.

#### Step 2.2: Implement ingestion state models (GREEN)

- **Task ID:** TASK-006
- **File:** `src\living_adr\core\ingestion.py`
- **Action:** Create
- **Changes:** Add `DeliveryStatus`, `IngestionErrorCategory`, `IngestionDelivery`, retry/dead-letter fields, normalized key fields, and state-transition helpers.

#### Step 2.3: Implement ingestion store contract/storage (GREEN)

- **Task ID:** TASK-007
- **File:** `src\living_adr\persistence\ingestion_store.py`
- **Action:** Create
- **Changes:** Add delivery id lookup/upsert, outcome update, evidence cache hooks, and fakeable interface; use SQLite if scaffold persistence exists, otherwise an interface plus in-memory implementation for tests with a clear SQLite follow-up in the same file.

#### Step 2.4: Add GitHub event filtering tests (RED)

- **Task ID:** TASK-008
- **File:** `tests\scm\test_github_event_filtering.py`
- **Action:** Create
- **Changes:** Test configured merged PR accepted, unconfigured repository rejected, non-PR event skipped, closed-unmerged skipped, opened/synchronized skipped, and malformed payload failed.

#### Step 2.5: Implement payload filtering and repository resolution (GREEN)

- **Task ID:** TASK-009
- **File:** `src\living_adr\scm\github_webhook.py`
- **Action:** Modify
- **Changes:** Parse verified JSON payload, extract repository identity candidate, resolve against `LivingADRConfig`, and return accepted/skipped/rejected merged-PR intake data.

#### Step 2.6: Wire idempotency into webhook handler (GREEN)

- **Task ID:** TASK-010
- **File:** `src\living_adr\apps\workflow_service\webhooks.py`
- **Action:** Modify
- **Changes:** Check delivery store before processing, persist first-seen delivery state before downstream fetches, and return prior outcome on duplicate delivery ids.

### Phase 3: Normalize SCMEvent and provider seam

#### Step 3.1: Add SCMEvent contract tests (RED)

- **Task ID:** TASK-011
- **File:** `tests\core\test_scm_event.py`
- **Action:** Create
- **Changes:** Test required repository scope, provider delivery id, normalized PR key format, PR number, refs, timestamps, merge SHA, fetch handles, and provider-neutral field names.

#### Step 3.2: Implement core SCM contracts (GREEN)

- **Task ID:** TASK-012
- **File:** `src\living_adr\core\scm.py`
- **Action:** Create
- **Changes:** Add provider enum, `SCMEvent`, fetch handle value objects, `SCMProvider` protocol, `PullRequestMetadata`, `ChangedFileMetadata`, `DiffEvidence`, and `CandidateEvidence` or evidence precursor types.

#### Step 3.3: Add GitHub normalization tests (RED)

- **Task ID:** TASK-013
- **File:** `tests\scm\test_github_event_normalization.py`
- **Action:** Create
- **Changes:** Test accepted GitHub merged PR payload normalizes into `SCMEvent` with repository scope and fetch handles while provider-specific raw fields remain in metadata.

#### Step 3.4: Implement GitHub event normalizer (GREEN)

- **Task ID:** TASK-014
- **File:** `src\living_adr\scm\github_webhook.py`
- **Action:** Modify
- **Changes:** Convert accepted intake data to `SCMEvent`; derive normalized PR key from provider, repository canonical key/repo id, PR number, and merge SHA or closed timestamp fallback.

#### Step 3.5: Export SCM contracts

- **Task ID:** TASK-015
- **Files:** `src\living_adr\core\__init__.py`, `src\living_adr\scm\__init__.py`
- **Action:** Modify/Create
- **Changes:** Export stable core contracts and GitHub adapter helpers according to package conventions without exporting raw payload internals.

### Phase 4: Fetch minimal PR/diff candidate evidence

#### Step 4.1: Add GitHub provider tests (RED)

- **Task ID:** TASK-016
- **File:** `tests\scm\test_github_provider.py`
- **Action:** Create
- **Changes:** Use fake HTTP/GitHub client responses to test PR metadata fetch, changed-file list fetch, diff fetch/handle, permission error, rate-limit error, missing PR, and transient failure classification.

#### Step 4.2: Implement GitHubProvider adapter (GREEN)

- **Task ID:** TASK-017
- **File:** `src\living_adr\scm\github_provider.py`
- **Action:** Create
- **Changes:** Implement `SCMProvider` methods with repository-scoped installation context, fakeable client abstraction, minimal endpoint usage, and provider-error mapping.

#### Step 4.3: Add candidate evidence tests (RED)

- **Task ID:** TASK-018
- **File:** `tests\workflow\test_candidate_evidence.py`
- **Action:** Create
- **Changes:** Test evidence builder links `SCMEvent`, PR metadata, changed files, diff summary/handle, provider delivery id, normalized PR key, and immutable provenance.

#### Step 4.4: Implement evidence builder and cache updates (GREEN)

- **Task ID:** TASK-019
- **Files:** `src\living_adr\workflow\ingestion.py`, `src\living_adr\persistence\ingestion_store.py`
- **Action:** Create/Modify
- **Changes:** Build candidate evidence from `SCMEvent` and provider responses; persist/cache evidence by normalized PR key and delivery id; avoid duplicate API work when evidence already exists.

#### Step 4.5: Wire evidence collection into handler (GREEN)

- **Task ID:** TASK-020
- **File:** `src\living_adr\apps\workflow_service\webhooks.py`
- **Action:** Modify
- **Changes:** After normalization, invoke evidence builder/provider, update delivery status, and expose a handoff result ready for downstream classifiers/workflow nodes.

### Phase 5: Replay and dead-letter recovery

#### Step 5.1: Add replay/dead-letter tests (RED)

- **Task ID:** TASK-021
- **File:** `tests\workflow\test_replay_dead_letter.py`
- **Action:** Create
- **Changes:** Test retryable provider failure, poison/malformed dead-letter, replay of stored accepted delivery, replay of failed fetch after provider recovers, and duplicate replay idempotency.

#### Step 5.2: Implement replay service (GREEN)

- **Task ID:** TASK-022
- **File:** `src\living_adr\workflow\replay.py`
- **Action:** Create
- **Changes:** Add replay orchestration over stored delivery/event/evidence records, reusing the same normalizer/provider/evidence builder and preserving idempotency semantics.

#### Step 5.3: Implement dead-letter transitions (GREEN)

- **Task ID:** TASK-023
- **Files:** `src\living_adr\core\ingestion.py`, `src\living_adr\persistence\ingestion_store.py`
- **Action:** Modify
- **Changes:** Add retry count, next action, dead-letter status, error category metadata, and transition helpers for retryable versus poison outcomes.

#### Step 5.4: Add operator replay entry point (GREEN)

- **Task ID:** TASK-024
- **File:** `src\living_adr\apps\workflow_service\replay.py`
- **Action:** Create
- **Changes:** Add a callable/CLI-compatible replay entry point if app conventions support it; otherwise expose a documented function used by tests and future operator wiring.

### Phase 6: Observability and integration verification

#### Step 6.1: Add observability metadata tests (RED)

- **Task ID:** TASK-025
- **File:** `tests\workflow\test_ingestion_observability.py`
- **Action:** Create
- **Changes:** Test verification, duplicate, skipped, accepted, fetch failure, replay, and dead-letter observations include allowed metadata keys and exclude raw body/diff/secret content.

#### Step 6.2: Add metadata-only instrumentation (GREEN)

- **Task ID:** TASK-026
- **Files:** `src\living_adr\apps\workflow_service\webhooks.py`, `src\living_adr\workflow\ingestion.py`, `src\living_adr\workflow\replay.py`, `src\living_adr\scm\github_provider.py`
- **Action:** Modify
- **Changes:** Record events/counters/spans through Feature 002 `Observability` port for HMAC outcome, idempotency outcome, normalization, fetch, evidence creation, replay, and dead-letter.

#### Step 6.3: Add fake end-to-end ingestion test (RED)

- **Task ID:** TASK-027
- **File:** `tests\workflow\test_github_webhook_ingestion_e2e.py`
- **Action:** Create
- **Changes:** Test valid signed merged PR delivery produces one `SCMEvent` and one candidate evidence bundle, then duplicate delivery returns prior result without provider refetch.

#### Step 6.4: Final handler integration fixes (GREEN)

- **Task ID:** TASK-028
- **Files:** `src\living_adr\apps\workflow_service\webhooks.py`, `src\living_adr\workflow\ingestion.py`, `src\living_adr\persistence\ingestion_store.py`
- **Action:** Modify
- **Changes:** Resolve integration gaps found by end-to-end test; keep fixes limited to ingestion path and avoid classifier/ADR drafting scope.

#### Step 6.5: Run unit tests

- **Task ID:** TASK-029
- **Files:** `tests\apps\test_github_webhook_endpoint.py`, `tests\core\test_scm_event.py`, `tests\scm\test_github_webhook_signature.py`, `tests\scm\test_github_event_filtering.py`, `tests\scm\test_github_event_normalization.py`, `tests\scm\test_github_provider.py`, `tests\workflow\test_ingestion_idempotency.py`, `tests\workflow\test_candidate_evidence.py`, `tests\workflow\test_replay_dead_letter.py`, `tests\workflow\test_ingestion_observability.py`, `tests\workflow\test_github_webhook_ingestion_e2e.py`
- **Action:** Verify
- **Changes:** Run existing pytest command and fix only failures caused by this feature.

#### Step 6.6: Run lint and seam checks

- **Task ID:** TASK-030
- **Files:** `src\living_adr\core\scm.py`, `src\living_adr\core\ingestion.py`, `src\living_adr\scm\github_webhook.py`, `src\living_adr\scm\github_provider.py`, `src\living_adr\workflow\ingestion.py`, `src\living_adr\workflow\replay.py`
- **Action:** Verify
- **Changes:** Run existing Ruff command; confirm workflow-facing modules do not traverse raw GitHub payloads and observability has no raw body/diff exports.

## Complexity Tracking

| Phase | Files Changed | New Files | Estimated Effort | Risk |
|---|---:|---:|---|---|
| Phase 1 | 0 | 4 | Medium | High security boundary |
| Phase 2 | 2 | 3 | Medium | High idempotency boundary |
| Phase 3 | 2 | 2 | Medium | High contract/seam risk |
| Phase 4 | 2 | 3 | Medium | Medium external API/rate-limit risk |
| Phase 5 | 2 | 2 | Medium | Medium replay safety risk |
| Phase 6 | 4 | 2 | Low | Medium trace hygiene/integration risk |

## Dependencies & Prerequisites

- Feature 002 implementation exists or is stubbed sufficiently to import `RepositoryIdentity`, `RepositoryConfig`, config startup snapshot, and `Observability`.
- GitHub webhook secret and GitHub App credentials are supplied through env/vault at runtime, not repository config.
- If no HTTP/GitHub client is available, add one through uv in a separate, locked dependency change.
- No live GitHub access is required for unit tests; all provider behavior must be fakeable.
- Feature 015 may later consume the handoff contract; do not implement full LangGraph checkpointing here.

## Rollback Strategy

- Phase 1 rollback: remove webhook route/helper and tests; no persisted state migration should exist yet.
- Phase 2 rollback: remove ingestion state/store and idempotency wiring; ensure no partial duplicate-processing path remains enabled.
- Phase 3 rollback: remove exported SCM contracts only if downstream features have not consumed them; otherwise keep compatibility shims.
- Phase 4 rollback: disable provider fetch/evidence builder behind the handler and keep verified/idempotent delivery state intact for replay later.
- Phase 5 rollback: remove operator replay entry point while retaining dead-letter records for manual inspection.
- Phase 6 rollback: remove observability instrumentation if it causes failures, but keep behavior tests and no raw trace export checks.

## Machine-Readable Task Graph

```yaml
task_graph:
  - id: TASK-001
    slice: 1
    story: US-1
    depends_on: []
    parallelizable_with: []
    files: [tests\scm\test_github_webhook_signature.py]
  - id: TASK-002
    slice: 1
    story: US-1
    depends_on: [TASK-001]
    parallelizable_with: []
    files: [src\living_adr\scm\github_webhook.py]
  - id: TASK-003
    slice: 1
    story: US-1
    depends_on: [TASK-002]
    parallelizable_with: []
    files: [tests\apps\test_github_webhook_endpoint.py]
  - id: TASK-004
    slice: 1
    story: US-1
    depends_on: [TASK-003]
    parallelizable_with: []
    files: [src\living_adr\apps\workflow_service\webhooks.py]
  - id: TASK-005
    slice: 2
    story: US-2
    depends_on: [TASK-004]
    parallelizable_with: []
    files: [tests\workflow\test_ingestion_idempotency.py]
  - id: TASK-006
    slice: 2
    story: US-2
    depends_on: [TASK-005]
    parallelizable_with: []
    files: [src\living_adr\core\ingestion.py]
  - id: TASK-007
    slice: 2
    story: US-2
    depends_on: [TASK-006]
    parallelizable_with: []
    files: [src\living_adr\persistence\ingestion_store.py]
  - id: TASK-008
    slice: 2
    story: US-2
    depends_on: [TASK-007]
    parallelizable_with: []
    files: [tests\scm\test_github_event_filtering.py]
  - id: TASK-009
    slice: 2
    story: US-2
    depends_on: [TASK-008]
    parallelizable_with: []
    files: [src\living_adr\scm\github_webhook.py]
  - id: TASK-010
    slice: 2
    story: US-2
    depends_on: [TASK-009]
    parallelizable_with: []
    files: [src\living_adr\apps\workflow_service\webhooks.py]
  - id: TASK-011
    slice: 3
    story: US-3
    depends_on: [TASK-010]
    parallelizable_with: []
    files: [tests\core\test_scm_event.py]
  - id: TASK-012
    slice: 3
    story: US-3
    depends_on: [TASK-011]
    parallelizable_with: []
    files: [src\living_adr\core\scm.py]
  - id: TASK-013
    slice: 3
    story: US-3
    depends_on: [TASK-012]
    parallelizable_with: []
    files: [tests\scm\test_github_event_normalization.py]
  - id: TASK-014
    slice: 3
    story: US-3
    depends_on: [TASK-013]
    parallelizable_with: []
    files: [src\living_adr\scm\github_webhook.py]
  - id: TASK-015
    slice: 3
    story: US-3
    depends_on: [TASK-014]
    parallelizable_with: []
    files: [src\living_adr\core\__init__.py, src\living_adr\scm\__init__.py]
  - id: TASK-016
    slice: 4
    story: US-4
    depends_on: [TASK-015]
    parallelizable_with: []
    files: [tests\scm\test_github_provider.py]
  - id: TASK-017
    slice: 4
    story: US-4
    depends_on: [TASK-016]
    parallelizable_with: []
    files: [src\living_adr\scm\github_provider.py]
  - id: TASK-018
    slice: 4
    story: US-4
    depends_on: [TASK-017]
    parallelizable_with: []
    files: [tests\workflow\test_candidate_evidence.py]
  - id: TASK-019
    slice: 4
    story: US-4
    depends_on: [TASK-018]
    parallelizable_with: []
    files: [src\living_adr\workflow\ingestion.py, src\living_adr\persistence\ingestion_store.py]
  - id: TASK-020
    slice: 4
    story: US-4
    depends_on: [TASK-019]
    parallelizable_with: []
    files: [src\living_adr\apps\workflow_service\webhooks.py]
  - id: TASK-021
    slice: 5
    story: US-5
    depends_on: [TASK-020]
    parallelizable_with: []
    files: [tests\workflow\test_replay_dead_letter.py]
  - id: TASK-022
    slice: 5
    story: US-5
    depends_on: [TASK-021]
    parallelizable_with: []
    files: [src\living_adr\workflow\replay.py]
  - id: TASK-023
    slice: 5
    story: US-5
    depends_on: [TASK-022]
    parallelizable_with: []
    files: [src\living_adr\core\ingestion.py, src\living_adr\persistence\ingestion_store.py]
  - id: TASK-024
    slice: 5
    story: US-5
    depends_on: [TASK-023]
    parallelizable_with: []
    files: [src\living_adr\apps\workflow_service\replay.py]
  - id: TASK-025
    slice: 6
    story: US-5
    depends_on: [TASK-024]
    parallelizable_with: []
    files: [tests\workflow\test_ingestion_observability.py]
  - id: TASK-026
    slice: 6
    story: US-5
    depends_on: [TASK-025]
    parallelizable_with: []
    files: [src\living_adr\apps\workflow_service\webhooks.py, src\living_adr\workflow\ingestion.py, src\living_adr\workflow\replay.py, src\living_adr\scm\github_provider.py]
  - id: TASK-027
    slice: 6
    story: US-1
    depends_on: [TASK-026]
    parallelizable_with: []
    files: [tests\workflow\test_github_webhook_ingestion_e2e.py]
  - id: TASK-028
    slice: 6
    story: US-1
    depends_on: [TASK-027]
    parallelizable_with: []
    files: [src\living_adr\apps\workflow_service\webhooks.py, src\living_adr\workflow\ingestion.py, src\living_adr\persistence\ingestion_store.py]
  - id: TASK-029
    slice: verification
    story: Verification
    depends_on: [TASK-028]
    parallelizable_with: [TASK-030]
    files: [tests\apps\test_github_webhook_endpoint.py, tests\core\test_scm_event.py, tests\scm\test_github_webhook_signature.py, tests\scm\test_github_event_filtering.py, tests\scm\test_github_event_normalization.py, tests\scm\test_github_provider.py, tests\workflow\test_ingestion_idempotency.py, tests\workflow\test_candidate_evidence.py, tests\workflow\test_replay_dead_letter.py, tests\workflow\test_ingestion_observability.py, tests\workflow\test_github_webhook_ingestion_e2e.py]
  - id: TASK-030
    slice: verification
    story: Verification
    depends_on: [TASK-028]
    parallelizable_with: [TASK-029]
    files: [src\living_adr\core\scm.py, src\living_adr\core\ingestion.py, src\living_adr\scm\github_webhook.py, src\living_adr\scm\github_provider.py, src\living_adr\workflow\ingestion.py, src\living_adr\workflow\replay.py]
```
