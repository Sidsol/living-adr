# Codebase Research: LivingADR Observability & Quality

> Greenfield planning research: no production `living-adr` code exists in scope for this feature folder. Findings are derived from the required project artifacts and feature 002's established contracts.

## Architecture Overview

LivingADR is planned as a single Python repository named `living-adr` with two deployable processes: `workflow-service` and `mcp-context-server`. Shared domain ports live under `src\living_adr\core`, while adapters live behind those ports. `architecture.md#tech-stack` selects LangSmith through a thin `Observability` wrapper and pins `langsmith 0.8.5`. `architecture.md#service-boundaries` assigns `Observability` to core and keeps implementations behind adapters.

Feature 002 establishes the exact `Observability` port and no-op implementation. Feature 013 must swap in a LangSmith implementation behind that port rather than redefining the port. The current no-op contract is metadata-first and dependency-free:

- `record_event(name, metadata)`
- `increment_counter(name, value, metadata)`
- `start_span(name, metadata) -> ContextManager[ObservationSpan]`

## Directory Structure

Planned repository layout from `..\..\architecture.md#tech-stack`:

```text
C:\repos\living-adr\
  pyproject.toml
  uv.lock
  src\living_adr\
    apps\workflow_service\
    apps\mcp_context_server\
    core\
    scm\
    graph\
    workflow\
    hitl\
    observability\
  tests\
  var\.gitkeep
```

Relevant planned files for this feature:

| Area | Expected purpose |
|---|---|
| `src\living_adr\core\observability.py` | Feature 002 port and no-op implementation; callers depend here. |
| `src\living_adr\observability\langsmith_adapter.py` | LangSmith-backed adapter behind the core port. |
| `src\living_adr\observability\redaction.py` | Metadata allowlist/redaction/default-deny raw export policy. |
| `src\living_adr\observability\metrics.py` | Shared metadata keys and helper events/counters. |
| `src\living_adr\observability\config.py` | LangSmith enablement, retention, sampling, raw export flags. |
| `src\living_adr\observability\evals\` | Retrieval/drafting evaluation fixtures and runners. |
| `tests\observability\` | Unit and adapter tests with fake LangSmith client. |
| `tests\evals\` | Evaluation harness tests and sample fixture tests. |

## Logic Flows

### Flow: Metadata trace emission

1. Entry point: instrumented workflow/HITL/MCP/drafting code calls `Observability.start_span(...)` or `record_event(...)` through the core port.
2. Adapter receives event/span metadata and normalizes repository key, run id, operation name, timestamps, status, and safe identifiers.
3. Redaction policy denies forbidden raw keys and redacts unsafe nested metadata.
4. If LangSmith is enabled, the adapter forwards safe metadata to LangSmith; otherwise the no-op adapter accepts the call.
5. Structured log emission mirrors the safe metadata for local diagnostics.

### Flow: Latency and token metrics

1. A stage opens an observation span for workflow, model call, retrieval, HITL decision handling, graph mutation, MCP answer, or evaluation.
2. On span exit, elapsed time is recorded in metadata and as a counter/event as supported by the port.
3. Model adapters pass token usage as numeric metadata only; prompt and response bodies remain forbidden.
4. Error and retry metadata are emitted by type/count, not by raw stack trace or payload.

### Flow: Draft decision and mutation monitoring

1. HITL review records approval, approved-after-edit, rejection, or deferral through `record_event`/`increment_counter`.
2. `ApprovalBoundMutationService` checks an `ApprovedReviewDecision` before mutation.
3. Failed checks emit an unauthorized-mutation event with safe identifiers and reason code.
4. Successful approved mutations emit decision id, mutation type, latency, and status metadata.

### Flow: Evaluation harness

1. Held-out query fixtures define repository key, question, optional code area, expected ADR ids/rationale references, and rubric metadata.
2. Retrieval evaluation calls `ArchitectureContextQuery.answer_why(...)` through a test/fake or local adapter and checks expected citations/coverage.
3. Drafting fixtures define structural-change evidence plus expected quality checks: evidence citation, alternatives, consequences, provisional-rationale labeling.
4. Evaluation output is machine-readable JSON/JSONL with per-case pass/fail and aggregate regression signals.
5. Evaluation runs emit observability metadata about harness version, fixture version, counts, and failures.

## Data Models

| Model | Source | Observability relevance |
|---|---|---|
| `RepositoryIdentity` | `..\..\architecture.md#data-model`; feature 002 | Required metadata scope for every trace, metric, audit, and eval case. |
| `RepositoryConfig` | `..\..\architecture.md#data-model`; feature 002 | May include optional per-repo retention/sampling overrides and external LLM allow/deny. |
| `SCMEvent` | `..\..\architecture.md#data-model` | Provides PR ids, delivery ids, and latency start time for SM-02. |
| `StructuralChange` / `ChangeEvidence` | `..\..\architecture.md#data-model` | Supplies change class and evidence identifiers for draft/eval metadata. |
| `ADRDraft` | `..\..\architecture.md#data-model` | Outcome tracking for SM-01; raw draft body must not be exported by default. |
| `ApprovalEvent` / `ApprovedReviewDecision` | `..\..\architecture.md#data-model` | Decision outcome, decision id, draft hash, and mutation authorization checks for SM-05. |
| `QuerySession` / `RetrievalTrace` | `..\..\architecture.md#data-model` | Query metadata, retrieved context IDs, cited ADRs, and quality signals under default-deny export. |
| `AuditEvent` | `..\..\architecture.md#data-model` | Source for mutation, review, publish, MCP access, and failed/retried operation observability. |

## Integration Points

| Integration | Type | Location | Notes |
|---|---|---|---|
| LangSmith | External observability SaaS/SDK | `src\living_adr\observability\langsmith_adapter.py` | Must receive metadata-only traces by default. |
| Structured logs | Local process logging | `src\living_adr\observability\logging.py` | Mirrors safe metadata for local and CI diagnostics. |
| LangGraph workflow | Internal instrumentation caller | `src\living_adr\workflow\...` | Emits run/stage spans and PR-to-draft latency. |
| Claude adapter | Internal instrumentation caller | `src\living_adr\workflow\...` or `src\living_adr\drafting\...` | Emits token usage and model latency, not prompt/response bodies. |
| HITL review | Internal instrumentation caller | `src\living_adr\hitl\...` | Emits review outcome metrics for SM-01. |
| ApprovalBoundMutationService | Internal instrumentation caller | `src\living_adr\graph\...` or `core` service | Emits unauthorized-mutation and successful approved mutation metrics for SM-05. |
| ArchitectureContextQuery | Internal eval target | `src\living_adr\graph\...` / MCP | Used by retrieval evaluation for SM-03/SM-04. |

## Configuration & Environment

Observed/planned configuration from `..\..\architecture.md#cross-cutting`:

- GitHub, Anthropic, LangSmith, UI token, storage path, and repository target settings come from environment variables or `.env.local`; scaffold creates `.env.example` but no secrets.
- `RepositoryConfig` carries no secrets.
- Default PoC observability sampling is 100% metadata traces due to low volume.
- Trace retention requirement is 30 days; implementation must validate or document operator compliance.
- Raw export is default-deny; opt-in debug export is allowed only when repository sensitivity policy allows it.

## Technical Debt & Observations

- Success metrics SM-03 and SM-04 are explicitly TBD in `vision.md`; the roadmap assigns the held-out query/evaluation harness to feature 013.
- `architecture.md#cross-cutting` distinguishes Anthropic as authoritative external data egress from LangSmith as observability sidecar; disabling LangSmith raw export does not prevent Claude egress.
- `architecture.md#anti-patterns` FM-21 and FM-22 are directly relevant: sensitive trace leakage and evaluation overfitting must be prevented.
- Feature 002 intentionally kept `Observability` thin; feature 013 should not force all instrumentation needs into a broad port change.
- Since the project is greenfield, tests must rely on fake clients and local fixture outputs rather than live LangSmith.

## Key Patterns

- Depend on core ports, not concrete adapters.
- Repository-scope every record and metric via `RepositoryIdentity`.
- Treat code/PR evidence as untrusted; export identifiers and summaries, not raw payloads.
- Use append-only audit and event-style observability for review/mutation lifecycle.
- Use versioned evaluation fixtures as regression signals, not as proof of absolute model quality.
