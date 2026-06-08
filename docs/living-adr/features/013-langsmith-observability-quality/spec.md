# Feature Specification: langsmith-observability-quality

## Overview

Feature 013 replaces the no-op `Observability` implementation established by feature 002 with a LangSmith-backed adapter behind the same core port. It adds structured logs, metadata-only traces, default-deny raw export controls, latency and token-count metrics, draft acceptance/rejection tracking, unauthorized-mutation checks, and a small evaluation harness for retrieval and drafting regression signals.

This feature serves TH-06 Observability & Quality Monitoring and owns the held-out query/evaluation support required to baseline SM-03 and SM-04. It must not redefine the `Observability` port; it binds to feature 002's core contract:

- `record_event(name: str, metadata: Mapping[str, object] | None = None) -> None`
- `increment_counter(name: str, value: int = 1, metadata: Mapping[str, object] | None = None) -> None`
- `start_span(name: str, metadata: Mapping[str, object] | None = None) -> ContextManager[ObservationSpan]`

## User Stories

### [US-1] Emit metadata-only LangSmith traces — Priority: P1

**As a** LivingADR operator, **I want** LangSmith traces and structured logs to contain safe metadata only by default, **so that** debugging does not leak raw code, prompts, drafts, retrieved context, reviewer comments, or secrets.

#### Acceptance Scenarios

- **Given** LangSmith credentials are configured, **When** workflow code emits events/spans through feature 002's `Observability` port, **Then** the LangSmith implementation records trace metadata without requiring callers to import LangSmith.
- **Given** metadata contains forbidden raw fields such as `raw_diff`, `prompt`, `draft_body`, `reviewer_comment`, `retrieved_context`, or `secret`, **When** the LangSmith adapter processes the event, **Then** those fields are rejected or redacted before export and a structured redaction event is logged.
- **Given** raw export is not explicitly enabled, **When** a trace is emitted for any repository, **Then** raw payload export remains denied.
- **Given** raw export is explicitly enabled for debugging but the repository is marked sensitive, **When** a trace is emitted, **Then** raw export is still denied.

### [US-2] Measure latency and token-count quality signals — Priority: P1

**As a** platform/DevEx owner, **I want** latency and token-count metrics for the LivingADR pipeline, **so that** SM-02 and cost/performance regressions can be detected.

#### Acceptance Scenarios

- **Given** a merged PR workflow run reaches drafting, HITL, retrieval, or MCP answer generation, **When** spans complete, **Then** latency metadata is emitted for each stage and the run as a whole.
- **Given** a Claude call reports token usage, **When** the call is observed, **Then** prompt, completion, and total token counts are emitted as metadata/counters without exporting prompt bodies or model responses.
- **Given** a run errors or retries, **When** the event is observed, **Then** error type and retry count are emitted without stack traces containing sensitive payloads.

### [US-3] Track draft outcomes and unauthorized-mutation checks — Priority: P1

**As a** tech lead/architect, **I want** draft decisions and mutation authorization failures tracked, **so that** SM-01 and SM-05 are measurable and audit anomalies are visible.

#### Acceptance Scenarios

- **Given** an ADR draft is approved, approved after edit, rejected, or deferred, **When** the review event is recorded, **Then** the outcome counter includes repository key, draft id, change class, decision outcome, and reviewer role metadata only.
- **Given** an `ApprovalBoundMutationService` rejects a missing, expired, reused, mismatched, or rejected decision, **When** the check fails, **Then** an unauthorized-mutation metric/event is emitted and linked by safe identifiers.
- **Given** graph mutation succeeds, **When** the audit-linked mutation is recorded, **Then** observability metadata includes `decision_id`, repository key, mutation type, latency, and success status but not ADR body text.

### [US-4] Provide retrieval and drafting evaluation harness — Priority: P1

**As a** LivingADR maintainer, **I want** a small versioned evaluation harness for retrieval and drafting, **so that** SM-03 retrieval relevance and SM-04 architecture question coverage can produce regression signals.

#### Acceptance Scenarios

- **Given** a held-out query fixture with expected ADR/rationale references, **When** the retrieval evaluation runs, **Then** it records relevance/coverage results, missing expected citations, and query-level pass/fail signals.
- **Given** an ADR drafting fixture with structural-change evidence and expected quality checks, **When** the drafting evaluation runs, **Then** it records whether evidence citation, alternatives, consequences, and provisional-rationale labeling are present.
- **Given** evaluation output changes from the previous baseline, **When** the harness completes, **Then** it returns a machine-readable regression signal suitable for CI or local review.

### [US-5] Configure retention, sampling, and safe local defaults — Priority: P2

**As a** LivingADR operator, **I want** predictable observability configuration, **so that** the PoC uses 100% safe metadata tracing while preserving a path to post-PoC sampling and retention controls.

#### Acceptance Scenarios

- **Given** no LangSmith API key is configured, **When** services start, **Then** the no-op implementation remains usable and startup does not fail solely because LangSmith is absent.
- **Given** LangSmith is enabled, **When** traces are emitted, **Then** retention/sampling settings are read from environment/config and default to 100% PoC metadata sampling with no raw export.
- **Given** retention exceeds the architecture requirement, **When** configuration is validated, **Then** startup or diagnostics surface an actionable warning/error.

## Functional Requirements

- [FR-1] Implement a LangSmith-backed adapter behind feature 002's `Observability` port without changing caller-facing method names.
- [FR-2] Emit structured logs and metadata traces for workflow runs, model calls, retrieval, HITL decisions, graph mutation checks, MCP answers, and evaluation runs.
- [FR-3] Enforce default-deny raw export for raw diffs, full prompts, full provisional ADR drafts, reviewer comments, retrieved context, code snippets, secrets, and personal data.
- [FR-4] Support opt-in debug raw export only when repository policy allows it and the repository is not marked sensitive.
- [FR-5] Emit latency metrics for PR-to-draft, stage spans, retrieval, drafting, review-decision handling, graph mutation, and MCP answer generation.
- [FR-6] Emit token-count metrics for Claude calls when usage metadata is available.
- [FR-7] Track draft acceptance, approved-after-edit, rejection, and deferral outcomes for SM-01.
- [FR-8] Track unauthorized-mutation check failures and successful approved mutations for SM-05 monitoring.
- [FR-9] Provide a versioned held-out query fixture format and retrieval evaluation runner for SM-03 and SM-04 regression signals.
- [FR-10] Provide a small drafting evaluation fixture format and runner for evidence/alternatives/consequences/provisional-rationale checks.
- [FR-11] Produce machine-readable evaluation output suitable for CI and local review.
- [FR-12] Preserve no-op behavior when LangSmith is disabled or unconfigured.

## Non-Functional Requirements

- [NFR-1] Security/privacy: metadata export is safe-by-default and never leaks raw source, prompts, drafts, comments, retrieved context, secrets, or personal data unless explicitly and safely enabled.
- [NFR-2] Maintainability: instrumentation remains behind `Observability`; application modules do not import LangSmith directly.
- [NFR-3] Testability: redaction, default-deny policy, metrics emission, decision tracking, unauthorized-mutation events, and evaluation harness outputs are unit-testable without network access.
- [NFR-4] Reliability: observability failures must not break primary workflow, HITL, graph mutation, or MCP read paths.
- [NFR-5] Evaluation discipline: metric changes are regression signals, not proof of truth; fixtures are versioned to avoid evaluation overfitting.

## Scope

### In Scope

- LangSmith adapter behind `Observability` from feature 002.
- Structured logs and metadata-only traces.
- Redaction/default-deny raw export policy and tests.
- Latency, token-count, draft-outcome, and unauthorized-mutation metrics.
- Small retrieval and drafting evaluation harness with versioned fixtures and machine-readable output.
- Local/CI command entry point for evaluations.

### Out of Scope

- Redefining or broadening the feature 002 `Observability` port for callers.
- Replacing Anthropic/Claude egress controls or prompt-budget enforcement owned by drafting features.
- Building dashboards, alerting, or enterprise LangSmith governance.
- Full Ragas integration, large benchmark suites, or human labeling UI.
- Changing graph, HITL, MCP, or workflow business logic except adding calls to the existing observability port.
- Exporting raw source code, diffs, prompts, provisional drafts, reviewer comments, or retrieved context by default.

## Success Criteria and Instrumentation

- [ ] **SM-01:** Draft outcome counters distinguish approved, approved-after-edit, rejected, and deferred drafts by repository and change class.
- [ ] **SM-02:** PR-to-draft and per-stage latency metrics are emitted and can be aggregated from metadata traces/logs.
- [ ] **SM-03:** Retrieval relevance evaluation runs against held-out queries and reports query-level relevance/regression signals.
- [ ] **SM-04:** Architecture question coverage evaluation reports answerable/unanswerable query counts with expected ADR/rationale references.
- [ ] **SM-05:** Unauthorized mutation attempts and approved mutation successes are tracked with safe identifiers and no raw ADR text.
- [ ] Metadata-only LangSmith traces are enforced and tested.
- [ ] Default-deny raw export is enforced and tested, including sensitive repository override.
- [ ] No application module imports LangSmith directly except observability adapter code.

## Dependencies

- **Feature dependency:** feature 002 provides `RepositoryIdentity`, `RepositoryConfig`, and the no-op `Observability` port. This feature swaps only the implementation behind that port.
- **Project artifacts:** `..\..\architecture.md#tech-stack`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#data-model`, `..\..\architecture.md#anti-patterns` (especially FM-21 trace leakage and FM-22 evaluation overfitting), `..\..\vision.md#6-success-metrics`, and `..\..\roadmap.md#5-mvp-cut-line`.
- **Downstream instrumentation consumers:** features 003, 008, 009, 010, 011, 012, and 015 can call the port as they land.

## Open Questions

- Exact environment variable names for LangSmith API key/project/endpoint should be finalized during implementation; plan assumes `LANGSMITH_*` conventions.
- Whether retention can be enforced programmatically through LangSmith project settings or must be documented as an operator check may depend on the LangSmith SDK/API available at implementation time.
- Initial SM-03/SM-04 thresholds remain TBD; this feature provides the harness and baseline output rather than declaring final production thresholds.
