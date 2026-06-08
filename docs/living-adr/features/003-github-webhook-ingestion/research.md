# Codebase Research: LivingADR webhook ingestion foundation

> **Vocabulary note:** The user requested exactly 8 feature-level planning artifacts, so codebase-discovered vocabulary is captured inline instead of a separate sidecar.

## Research Basis

LivingADR is a greenfield project described by CRISPY project artifacts rather than production code. The planning target is the future `living-adr` repository. Existing feature 002 planning establishes the configuration and observability seams this feature consumes. This research documents the current architecture and predecessor contracts objectively from the available project documents.

## Architecture Overview

LivingADR uses a hybrid single-repository, two-deployable architecture. `workflow-service` owns webhook receipt, signature verification, SCM event normalization, idempotency, LangGraph orchestration, HITL review state, audit logging, and approved publication workflow. `mcp-context-server` is read-only and depends on query ports, not SCM credentials or mutation services (`..\..\architecture.md#service-boundaries`).

Core owns provider-neutral domain types and ports: `RepositoryIdentity`, `SCMProvider`, graph ports, repositories, audit, and `Observability`. The SCM area starts with `GitHubProvider`; `AzureDevOpsProvider` is explicitly post-PoC and must map its provider-specific event model into the same normalized workflow concepts (`..\..\architecture.md#service-boundaries`).

The data model defines `SCMEvent` as the normalized, idempotent event envelope for merged PRs. It includes repository scope, provider delivery identity, timestamps, and fetch handles, not provider-specific business logic (`..\..\architecture.md#data-model`). `ChangeEvidence` is repository-scoped immutable evidence gathered from merged PR metadata, diff summaries, structural signals, linked text, and retrieval context; evidence remains separate from inferred rationale.

Cross-cutting concerns require GitHub webhook HMAC validation, minimum GitHub App permissions, idempotency by provider delivery id and normalized PR key, replayable failed workflow steps, and poison events in a SQLite dead-letter/outbox table (`..\..\architecture.md#cross-cutting`). Observability must default-deny raw diffs, prompts, drafts, reviewer comments, and retrieved context, exporting only structured metadata.

## Directory Structure

No production `living-adr` code was inspected for this feature because the project is greenfield at planning time. Existing planned structure from feature 002 and architecture implies these future areas:

| Planned area | Purpose | Source |
|---|---|---|
| `src\living_adr\core` | Domain models and ports: `RepositoryIdentity`, `SCMEvent`, `SCMProvider`, `ChangeEvidence`, `Observability`. | `..\..\architecture.md#service-boundaries`, feature 002 `intent.md` |
| `src\living_adr\apps\workflow_service` | FastAPI workflow entrypoint and startup boundary; appropriate home for webhook route/handler. | `..\..\architecture.md#service-boundaries`, feature 002 `plan.md` |
| `src\living_adr\scm` | Provider adapters, starting with `GitHubProvider`; future Azure DevOps adapter lives behind the same port. | `..\..\architecture.md#service-boundaries` |
| `src\living_adr\workflow` | LangGraph workflow nodes and later orchestration handoff; feature 015 owns durable checkpointing. | `..\..\feature-map.md` brief 015 |
| `tests\core`, `tests\apps`, `tests\scm`, `tests\workflow` | Pytest test suites for pure contracts, app handlers, adapters, and workflow intake behavior. | feature 002 `plan.md` conventions |

## Logic Flows

### Flow: Configured repository startup

1. Startup loads `living-adr.config.yaml` into typed `LivingADRConfig` using Feature 002's loader.
2. Each tracked repository has `RepositoryIdentity` plus GitHub App installation id, publication policy, target path/branch, and external LLM flag.
3. Startup fails on invalid configuration; hot reload is out of scope for PoC.
4. Downstream ingestion consumes the validated repository list rather than parsing YAML directly.

### Flow: Webhook ingress as specified by architecture

1. Entry point: `workflow-service` receives a merged PR webhook from a configured GitHub repository (`..\..\architecture.md#service-boundaries`).
2. The workflow-service verifies HMAC before trusting the payload (`..\..\architecture.md#cross-cutting`).
3. It normalizes the provider event into `SCMEvent`, scoped by `RepositoryIdentity` (`..\..\architecture.md#data-model`).
4. It fetches PR, diff, and changed files through `SCMProvider` rather than raw GitHub-specific workflow code (`..\..\architecture.md#service-boundaries`).
5. It hands normalized evidence to downstream LangGraph workflow nodes and stores state/audit in SQLite WAL (`..\..\architecture.md#service-boundaries`, `..\..\architecture.md#deployment`).

### Flow: Replay and failure handling

1. Provider delivery ids and normalized PR keys are persisted as idempotency anchors (`..\..\architecture.md#cross-cutting`).
2. Failed workflow steps remain replayable from stored evidence.
3. Poison events stay in a SQLite dead-letter/outbox table for manual replay.
4. Observability records metadata-only event/counter/span outcomes through the Feature 002 port.

## Data Models

### Model: RepositoryIdentity

- Location: planned `src\living_adr\core\repository.py` from feature 002.
- Fields: `host`, `owner`, `repo`, `repo_id`; canonical key `host/owner/repo`.
- Relationships: scope key for `RepositoryConfig`, `SCMEvent`, `ChangeEvidence`, graph records, MCP queries, audit, and observability metadata.

### Model: RepositoryConfig

- Location: planned `src\living_adr\core\config.py` from feature 002.
- Fields: `RepositoryIdentity`, provider type, GitHub App installation id, default branch, ADR target branch/path, publication policy, external LLM allow/deny.
- Relationships: ingestion must use it to accept only configured repositories and resolve provider installation context.

### Model: SCMEvent

- Location: architecture-level model in `..\..\architecture.md#data-model`; implementation planned in core.
- Fields: repository, provider delivery identity, timestamps, normalized PR key, fetch handles, provider metadata.
- Relationships: source event for structural classifiers, workflow orchestration, evidence records, replay state, and audit.

### Model: ChangeEvidence / candidate evidence

- Location: architecture-level model in `..\..\architecture.md#data-model`; implementation planned in core/workflow.
- Fields: repository, source PR evidence, diff summaries or handles, file metadata, provenance links.
- Relationships: consumed by features 004/005 classifiers; later ADR drafts cite it as evidence, not authoritative rationale.

### Model: AuditEvent / delivery state

- Location: architecture-level model in `..\..\architecture.md#data-model` and cross-cutting error handling.
- Fields: repository identity, event/action, timestamps, error category, retry count, outcome.
- Relationships: records webhook handling, failed/retried operations, and downstream workflow/audit linkage.

## Integration Points

| Integration | Type | Location | Notes |
|---|---|---|---|
| GitHub App webhooks | HTTP callback | `workflow-service` | Must verify HMAC and delivery id; receives merged PR events. |
| GitHub REST API | External REST API | `GitHubProvider` behind `SCMProvider` | Fetch PR metadata, changed files, and diff evidence. |
| SQLite WAL state/audit | Local database | workflow persistence | Stores workflow state, audit, idempotency, outbox/dead-letter. |
| Feature 002 config | Local YAML/env | core config loader | Supplies repository identity and GitHub App installation context. |
| Feature 002 Observability | Core port | `src\living_adr\core\observability.py` | No-op initially; metadata-only events/counters/spans. |
| Azure DevOps service hooks | Future HTTP callback/API | future adapter | Different event taxonomy; must not leak into normalized workflow model. |

## Configuration & Environment

Architecture cross-cutting configuration includes repository target, GitHub App ID, private key path, webhook secret, Anthropic key, LangSmith key, UI token, storage paths, ADR publication policy, target branch, and path template. Feature 002 separates repository config from secrets: `RepositoryConfig` carries no secrets; webhook secret and GitHub private key are environment/vault concerns.

Webhook ingestion specifically needs:

- Validated `RepositoryConfig` list from Feature 002.
- GitHub webhook secret reference/value from env/vault.
- GitHub App credentials for `GitHubProvider` API calls.
- SQLite storage path for idempotency, replay, and dead-letter state.
- `Observability` implementation injected from core.

## Technical Debt & Observations

- The exact local PoC webhook delivery path is still an architectural open question: tunnel, relay, manual replay fixture, or hosted endpoint (`..\..\architecture.md#open-architectural-questions`).
- Exact GitHub App permissions are still open; least-privilege should be finalized during implementation/onboarding.
- Feature 015 owns durable LangGraph checkpointing; this feature should avoid duplicating full workflow orchestration while still persisting ingestion state.
- Feature 013 owns LangSmith implementation; this feature should only emit metadata through the inherited port.
- Feature 011 needs GitHub provider capability later for ADR publish-back, so provider design must avoid being narrowly read-only if the port family will also support writes later.

## Key Patterns

- **Ports and adapters:** core defines provider-neutral ports; adapters own external service details.
- **Repository scoping everywhere:** every domain record and external call accepts `RepositoryIdentity`.
- **Evidence before rationale:** PR data and diffs are evidence; approved ADRs are authoritative rationale; graph records are projections.
- **Approval-bound mutation:** graph mutations are impossible without `ApprovedReviewDecision`; ingestion only produces evidence.
- **Metadata-only observability:** raw payloads, diffs, prompts, drafts, and reviewer comments are default-deny trace data.
- **Replayable state:** provider delivery ids, normalized event keys, and dead-letter records are first-class for operational recovery.

## Research Findings Carried Forward

- `..\..\architecture.md#anti-patterns` FM-17 directly requires provider delivery IDs, normalized event keys, idempotent handlers, and manual replay.
- FM-18 requires minimal merged-PR evidence fetches and defers broad history mining.
- FM-24 requires provider-specific GitHub/Azure DevOps taxonomies to remain inside SCM adapters.
- Feature 002's no-op `Observability` port contract is the instrumentation dependency; no LangSmith dependency should be introduced by this feature.
