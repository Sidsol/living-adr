# Architecture Intent: github-webhook-ingestion

## Current State

LivingADR is greenfield. Project architecture assigns webhook receipt, signature verification, SCM event normalization, idempotency, and audit state to `workflow-service`; core owns `RepositoryIdentity`, `SCMProvider`, `SCMEvent`, `ChangeEvidence`, `AuditLog`, and `Observability`; `scm` starts with `GitHubProvider` while Azure DevOps remains a future adapter (`..\..\architecture.md#service-boundaries`).

Feature 002 provides the typed repository configuration seam and no-op observability port. No production GitHub webhook ingestion implementation exists yet. The architecture already requires HMAC validation, idempotency by provider delivery id and normalized PR key, replayable failed workflow steps, SQLite dead-letter/outbox state, minimal evidence fetches, and provider-neutral workflow concepts (`..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#anti-patterns`).

## Desired State

After this feature, `workflow-service` has a GitHub App webhook entry path that validates raw request signatures, filters to configured merged PR events, persists idempotent delivery state, normalizes accepted deliveries into `SCMEvent`, fetches minimal PR/diff evidence through `SCMProvider`/`GitHubProvider`, and emits replayable candidate evidence for downstream classifiers. All behavior is repository-scoped, observable through Feature 002's `Observability` port, and adapter-shaped so future Azure DevOps service hooks can map into the same normalized workflow model without GitHub leakage.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Webhook endpoint | Architecture assigns responsibility to `workflow-service`; no code yet | Raw-body GitHub webhook handler verifies `X-Hub-Signature-256` before parsing | Add app route/handler and HMAC verifier tests |
| Repository config consumption | Feature 002 planned typed config and startup loading | Ingestion resolves payload repository against `RepositoryConfig`/`RepositoryIdentity` | Inject config snapshot into webhook handling and reject unconfigured repos |
| Delivery idempotency | Architecture requires provider delivery IDs and replay | Persistent delivery store with accepted/skipped/failed/dead-letter states | Add ingestion state repository and duplicate-delivery behavior |
| Event normalization | `SCMEvent` described at architecture level | Core model with normalized PR key, repository scope, provider delivery id, timestamps, fetch handles | Implement model and normalizer |
| SCM provider seam | Architecture names `SCMProvider`/`GitHubProvider`; no methods yet | Minimal fetch methods for PR metadata, changed files, diff text/handle | Define port and GitHub adapter around REST/API client seam |
| Evidence stream | `ChangeEvidence` described at architecture level | Immutable candidate evidence for classifier features 004/005 | Add evidence builder and storage/cache seam |
| Replay/dead-letter | Architecture says failed steps replayable and poison events in SQLite outbox | Replay service/CLI function and dead-letter state transitions | Add replay API, retry/dead-letter classifications, tests |
| Observability | Feature 002 no-op port exists | Metadata-only instrumentation for verify/filter/idempotency/fetch/replay/dead-letter | Add calls without LangSmith dependency or raw payload export |
| Cross-SCM extensibility | Azure DevOps is future adapter | Provider-specific event details isolated in adapters/metadata | Avoid GitHub-only fields in workflow-facing APIs |

## Architecture Options

### Option A: FastAPI route parses GitHub payload directly in workflow nodes

**Approach:** Implement one webhook route that verifies HMAC, parses GitHub JSON, fetches PR data directly, and passes dictionaries into downstream workflow functions.

- ✅ Pros: Lowest initial code volume; quick PoC path.
- ❌ Cons: Leaks GitHub taxonomy into workflow; weak Azure DevOps seam; hard to test normalization separately; higher risk of duplicate side effects.
- 🔧 Effort: Low.

### Option B: Provider-neutral core event and SCMProvider port with GitHub adapter (selected)

**Approach:** Keep the FastAPI route thin. It verifies HMAC, records delivery state, resolves repository config, and calls a normalizer/provider adapter. Core exposes `SCMEvent`, `SCMProvider`, evidence records, and delivery-state interfaces. `GitHubProvider` owns GitHub REST and payload details.

- ✅ Pros: Aligns with `..\..\architecture.md#service-boundaries`; preserves Azure DevOps seam; enables isolated tests; supports idempotency and replay as first-class concepts; minimizes rate-limit waste.
- ❌ Cons: More files and contracts up front; must avoid over-generalizing the future Azure DevOps adapter.
- 🔧 Effort: Medium.

### Option C: Queue-first ingestion service with external broker

**Approach:** Webhook route verifies signatures and publishes raw/normalized messages to a durable external queue; workers perform normalization, fetches, retries, and dead-letter handling.

- ✅ Pros: Strong production scalability and replay semantics; decouples HTTP receive from slow API fetches.
- ❌ Cons: Violates PoC simplicity; adds infrastructure not in architecture; duplicates SQLite/WAL/checkpointing decisions; higher operational burden.
- 🔧 Effort: High.

## Selected Approach

**Option B: Provider-neutral core event and SCMProvider port with GitHub adapter.**

Rationale: Option B matches `..\..\architecture.md#service-boundaries` by putting domain types and ports in core, GitHub specifics in `scm`, and webhook receipt in `workflow-service`. It directly addresses `..\..\architecture.md#data-model` for `SCMEvent`/`ChangeEvidence`, `..\..\architecture.md#cross-cutting` for HMAC/idempotency/replay/dead-letter/observability, and `..\..\architecture.md#anti-patterns` FM-17, FM-18, and FM-24. It is substantial enough to avoid throwaway PoC code while not introducing external brokers or full orchestration owned by later feature 015.

## Module Surface Analysis

| Module | Inputs | Callers | Deletion test | Isolated-test candidate |
|---|---:|---|---|---|
| `src\living_adr\core\scm.py` | Provider, repository identity, PR refs/handles | webhook normalizer, classifiers, future publish-back | Deleting forces raw GitHub dicts through workflow | Yes — pure models/protocols |
| `src\living_adr\core\ingestion.py` | delivery id, event type, state, timestamps, errors | webhook handler, replay service, tests | Deleting removes idempotency/replay contract | Yes — pure state transitions |
| `src\living_adr\apps\workflow_service\webhooks.py` | raw request body, headers, config, stores, observability | FastAPI app/router | Deleting removes external ingestion entrypoint | Partially — test with ASGI client/fakes |
| `src\living_adr\scm\github_webhook.py` | GitHub headers/payload JSON | webhook handler | Deleting loses HMAC and event filtering | Yes — deterministic fixtures |
| `src\living_adr\scm\github_provider.py` | installation credentials, repository identity, PR handles | evidence builder, future publish-back | Deleting prevents GitHub API evidence fetch | Yes with fake HTTP/client; no live GitHub |
| `src\living_adr\workflow\ingestion.py` | `SCMEvent`, provider, delivery store | webhook handler, replay service, feature 015 handoff | Deleting prevents evidence stream creation | Yes with fake provider/store |
| `src\living_adr\workflow\replay.py` | stored delivery/event id, stores, provider | CLI/operator action, tests | Deleting makes FM-17 recovery impossible | Yes with fake stores/provider |
| `src\living_adr\persistence\ingestion_store.py` | SQLite connection/path, delivery/evidence records | webhook handler, replay, tests | Deleting removes durable idempotency/dead-letter | Partially — integration tests with temp project DB |
| `tests\scm\test_github_webhook.py` | fixture headers/payloads | pytest | Deleting risks HMAC/filter regressions | n/a |
| `tests\workflow\test_ingestion_flow.py` | fake config/provider/store | pytest | Deleting risks duplicate/evidence regressions | n/a |
| `tests\workflow\test_replay_dead_letter.py` | fake/stub stores | pytest | Deleting risks replay/dead-letter regressions | n/a |

## Ingestion Contract

The implementation should expose a small stable seam:

- `SCMEvent`: repository-scoped normalized merged-PR event with `provider`, `provider_event_type`, `provider_delivery_id`, `normalized_event_key`, `pr_number`, refs, merge commit SHA, delivery timestamp, and fetch handles.
- `SCMProvider`: provider-neutral port with methods such as `fetch_pull_request(repository, event_handle)`, `fetch_changed_files(repository, event_handle)`, and `fetch_diff(repository, event_handle)` or an equivalent diff handle method.
- `IngestionDelivery`: persisted delivery state keyed by provider delivery id and repository/provider where known.
- `CandidateEvidence`: immutable evidence bundle linked to `SCMEvent`, changed file metadata, diff summary/handle, PR title/body metadata, and provenance.
- `ReplayService`: reprocesses stored delivery/event records while preserving idempotency.

## Anti-Patterns to Avoid

- **Parsing JSON before HMAC verification:** tempting in FastAPI convenience handlers, but violates the raw-body trust boundary.
- **Using PR number alone as idempotency key:** PR numbers can collide across repositories/providers; delivery id and normalized repository-scoped event key are required.
- **Passing raw GitHub payloads into classifiers:** quick to implement, but violates FM-24 and blocks Azure DevOps seam.
- **Fetching full repository history or broad file content:** may improve context, but violates FM-18; fetch only V1 merged-PR evidence.
- **Treating evidence as rationale:** PR/diff data is evidence only; downstream HITL-approved ADRs become authoritative rationale.
- **Exporting webhook bodies/diffs to observability:** raw payloads and diffs are default-deny under `..\..\architecture.md#cross-cutting`.
- **Building full LangGraph checkpointing here:** feature 015 owns durable orchestration; this feature should hand off normalized events/evidence.
- **Hardcoding GitHub-only fields in `SCMEvent`:** provider-specific data belongs in adapter metadata or fetch handles.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add workflow-service webhook handler, core SCM/event/evidence contracts, GitHub adapter, ingestion persistence/replay seams, and tests | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HMAC verification accidentally uses parsed/re-serialized body | Medium | High | Verify against raw request bytes; test whitespace/order changes and invalid signatures. |
| Duplicate deliveries create duplicate evidence | Medium | High | Persist provider delivery id before side effects; test exact duplicate and replay paths. |
| GitHub event shape leaks into workflow/classifiers | Medium | High | Keep raw payload access in `scm\github_webhook.py`; expose only `SCMEvent`/evidence. |
| Rate limit or permission errors poison the workflow | Medium | Medium | Classify provider errors; cache fetched artifacts; dead-letter with retry metadata. |
| Replay bypasses authentication assumptions | Low | Medium | Replay only stored prior deliveries/events and mark replay source in audit/observability. |
| Azure DevOps seam over-generalizes too early | Medium | Medium | Normalize only fields needed for merged PR classifiers; keep provider metadata opaque. |
| Observability leaks raw diffs or secrets | Medium | High | Use typed metadata builders and tests/greps for raw body/diff export. |
| Persistence design conflicts with feature 015 checkpointing | Medium | Medium | Keep ingestion store focused on delivery/evidence/outbox; expose handoff contract for feature 015. |
