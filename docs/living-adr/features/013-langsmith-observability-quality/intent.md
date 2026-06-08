# Architecture Intent: langsmith-observability-quality

## Current State

LivingADR is greenfield. The architecture selects LangSmith through a thin `Observability` wrapper in `..\..\architecture.md#tech-stack`, and `..\..\architecture.md#service-boundaries` places the `Observability` port in core. Feature 002 establishes the exact no-op `Observability` port in `src\living_adr\core\observability.py` with `record_event`, `increment_counter`, and `start_span`; feature 013 must bind to that port and swap in an implementation, not redefine it.

`..\..\architecture.md#cross-cutting` requires structured logs, LangSmith metadata traces, default-deny raw export, 30-day retention, 100% PoC sampling, restricted LangSmith access, and opt-in raw export only under safe repository policy. `..\..\architecture.md#data-model` names `QuerySession` / `RetrievalTrace`, `AuditEvent`, `ApprovalEvent`, `ApprovedReviewDecision`, `ADRDraft`, and repository-scoped records that provide instrumentation metadata. `..\..\architecture.md#anti-patterns` explicitly calls out FM-21 sensitive data in traces and FM-22 evaluation overfitting.

## Desired State

LivingADR services continue to call the feature 002 `Observability` port, while dependency injection supplies either `NoOpObservability` or a LangSmith-backed adapter. The adapter enforces safe metadata export by default, emits structured logs, records latency/token/decision/mutation metrics, and runs a small versioned evaluation harness for retrieval and drafting regression signals. SM-01 through SM-05 become instrumentable, with SM-03/SM-04 evaluation harness ownership in this feature.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Port binding | Feature 002 no-op `Observability` port exists | LangSmith adapter implements same port | Add adapter and provider wiring without caller imports of LangSmith |
| Trace safety | Architecture policy only | Enforced default-deny redaction and metadata allowlist | Add redaction/policy module and tests |
| Structured logs | Required by architecture | Safe event/span metadata logged locally | Add logging helper integrated with adapter |
| Latency metrics | SM-02 target exists | Stage and PR-to-draft latency emitted | Add span timing and helper metadata conventions |
| Token metrics | Claude selected by architecture | Numeric token counts emitted | Add helper APIs/events for model-call usage metadata |
| Draft outcomes | SM-01 target exists | Approve/edit/reject/defer counters emitted | Add outcome event helpers and tests |
| Unauthorized mutations | SM-05 target exists | Failed authorization checks are observed | Add mutation-check events with reason codes |
| Retrieval quality | SM-03 TBD | Held-out query harness reports relevance/regression | Add fixture schema and runner |
| Question coverage | SM-04 TBD | Harness reports answerable/unanswerable coverage | Add expected-reference checks and aggregate output |
| Evaluation overfitting | FM-22 noted | Versioned fixtures and regression framing | Add metadata/version fields and checklist gates |

## Architecture Options

### Option A: Keep no-op port and add ad hoc logs only

**Approach:** Leave `NoOpObservability` as-is and ask each feature to log its own structured messages.

- ✅ Pros: Lowest implementation effort; no external dependency use.
- ❌ Cons: Does not satisfy LangSmith architecture choice, scatters metadata conventions, makes SM-03/SM-04 harness ownership unclear, and risks inconsistent redaction.
- 🔧 Effort: Low.

### Option B: LangSmith adapter behind feature 002 port with centralized redaction (selected)

**Approach:** Implement `LangSmithObservability` in `src\living_adr\observability`, inject it where configured, enforce default-deny metadata policy centrally, mirror safe metadata to structured logs, and add evaluation runners under the same package.

- ✅ Pros: Preserves port boundary; aligns with `..\..\architecture.md#tech-stack`; centralizes FM-21 controls; keeps instrumentation lightweight; testable with fake client; supports gradual feature-by-feature instrumentation.
- ❌ Cons: The feature 002 port is intentionally thin, so helper functions must map rich events into metadata without changing the port.
- 🔧 Effort: Medium.

### Option C: Full OpenTelemetry/Phoenix abstraction plus LangSmith exporter

**Approach:** Introduce a broader telemetry layer using OpenTelemetry GenAI semantics, with LangSmith as one sink and Phoenix/OpenTelemetry as future sinks.

- ✅ Pros: Strong long-term interoperability; richer metric semantics and ecosystem compatibility.
- ❌ Cons: Over-engineered for PoC; risks redefining the already-established port; increases dependencies and policy surface before initial metrics are proven.
- 🔧 Effort: High.

## Selected Approach

**Option B: LangSmith adapter behind feature 002 port with centralized redaction.**

Rationale: The architecture explicitly chooses LangSmith for V1 (`..\..\architecture.md#tech-stack`) while requiring a wrapper to enable redaction and future alternatives. Option B preserves the exact dependency contract from feature 002, satisfies `..\..\architecture.md#cross-cutting` default-deny raw export, and directly addresses `..\..\architecture.md#anti-patterns` FM-21/FM-22 without expanding the system into a full telemetry platform.

## Port Binding and Adapter Contract

Feature 013 binds to feature 002's port:

- `record_event(name, metadata)` becomes a safe structured event and, when enabled, a LangSmith trace/run metadata update.
- `increment_counter(name, value, metadata)` becomes a safe counter-like event/log entry. If LangSmith metrics support is unavailable or unsuitable, counters remain structured metadata events for aggregation.
- `start_span(name, metadata)` returns a context manager that measures elapsed time and emits safe start/end/error metadata.

No workflow, HITL, graph, MCP, SCM, or drafting module may import LangSmith directly. They import only the core `Observability` port and optional local helper functions that also depend on the port.

## Module Surface Analysis

| Module | Inputs | Callers | Deletion test | Isolated-test candidate |
|---|---:|---|---|---|
| `src\living_adr\observability\config.py` | env/settings, `RepositoryConfig` sensitivity/override fields | app startup, adapter factory | Deleting prevents LangSmith enablement, sampling, raw-export decisions | Yes — pure config validation |
| `src\living_adr\observability\redaction.py` | metadata mappings, repository policy | LangSmith adapter, structured logger, tests | Deleting risks FM-21 trace leakage | Yes — pure allow/deny/redaction matrix |
| `src\living_adr\observability\langsmith_adapter.py` | core port calls, fake/real LangSmith client, redaction policy | app bootstrap via dependency injection | Deleting leaves only no-op implementation and no LangSmith traces | Yes — fake client tests no network |
| `src\living_adr\observability\logging.py` | safe metadata events | adapter and eval runner | Deleting removes local structured diagnostics | Yes — capture log records |
| `src\living_adr\observability\metrics.py` | domain ids/outcomes/token usage | workflow/HITL/graph/MCP helper callers | Deleting scatters metric names and keys | Yes — helper output tests |
| `src\living_adr\observability\evals\fixtures.py` | JSON/YAML fixture files | eval runners, tests | Deleting removes versioned eval schemas | Yes — parse/validation tests |
| `src\living_adr\observability\evals\retrieval.py` | fixtures, `ArchitectureContextQuery`, `Observability` | CLI/CI, maintainers | Deleting prevents SM-03/SM-04 signals | Yes — fake query adapter tests |
| `src\living_adr\observability\evals\drafting.py` | fixtures, draft generator/fake output, `Observability` | CLI/CI, maintainers | Deleting prevents drafting regression signals | Yes — deterministic fixture tests |
| `src\living_adr\apps\workflow_service\observability.py` | app settings, config | workflow startup | Deleting prevents adapter selection | Partially — fake settings/app tests |
| `tests\observability\*` | fake clients, fixture metadata | pytest | Deleting risks policy regressions | n/a |
| `tests\evals\*` | fixture files, fake query/draft adapters | pytest | Deleting risks harness regressions | n/a |

## Anti-Patterns to Avoid

- **Redefining `Observability`:** tempting to add many methods for convenience, but violates feature 002's dependency contract and couples callers to this feature.
- **LangSmith imports outside observability package:** makes later Phoenix/OpenTelemetry replacement expensive and bypasses redaction.
- **Raw trace payloads by default:** directly violates `..\..\architecture.md#cross-cutting` and FM-21.
- **Treating evaluation scores as truth:** FM-22 requires regression-signal framing; small held-out sets cannot prove quality.
- **Secret-bearing config fields:** LangSmith keys belong in env/vault, not `RepositoryConfig`.
- **Observability as control flow:** telemetry failures must not block workflows, approvals, graph mutations, or MCP reads.
- **Repository-agnostic metrics:** every metric/event must include repository scope where applicable.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add observability adapter/config/redaction/eval modules, app wiring, and tests; add evaluation fixture examples | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Sensitive data leaks to LangSmith | Medium | High | Central default-deny redaction, forbidden-key tests, sensitive repository override, no direct LangSmith imports outside adapter |
| Thin port cannot express every metric cleanly | Medium | Medium | Use stable metadata conventions and helper functions that call existing methods; do not change caller-facing port |
| LangSmith SDK behavior differs from assumptions | Medium | Medium | Wrap client behind small adapter and fake client tests; fail closed to no-op/log-only behavior |
| Evaluation harness overfits small fixtures | Medium | Medium | Version fixtures, include edge/rejected examples, report regression signals not absolute truth |
| Telemetry failure breaks user flow | Low | High | Catch/log adapter errors and never raise from normal observability calls |
| Retention cannot be enforced via SDK | Medium | Medium | Validate configured intent where possible and surface operator diagnostic when enforcement is manual |
