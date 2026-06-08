# Quality Checklist: langsmith-observability-quality

## CRISPY Phase Gates

### 🔬 C — Research

- [ ] `research.md` documents the greenfield current state and required project artifacts.
- [ ] Research identifies feature 002's exact `Observability` port methods.
- [ ] Research maps planned modules, flows, data models, integrations, and configuration.
- [ ] Research cites relevant architecture anchors: `#tech-stack`, `#cross-cutting`, `#data-model`, and `#anti-patterns`.
- [ ] Research explicitly notes FM-21 trace leakage and FM-22 evaluation overfitting.

### 🎯 R — Sound Intent

- [ ] Gap analysis maps current no-op observability to LangSmith-backed desired state.
- [ ] At least 3 architecture options were evaluated.
- [ ] Selected approach preserves feature 002's `Observability` port without redefining it.
- [ ] Module Surface Analysis lists new/modified modules and isolated-test candidates.
- [ ] Anti-patterns include direct LangSmith imports outside observability, raw trace payloads, and evaluation-overfitting claims.
- [ ] Affected repository is listed with confidence.

### 🍕 I — Vertical Slices

- [ ] `outline.md` contains exactly 5 slices.
- [ ] Each slice delivers independently testable behavior.
- [ ] Slice dependencies are mapped in human-readable and machine-readable graphs.
- [ ] Every slice includes `automation: HITL | AFK` and `automation_reason`.
- [ ] Slice 2 owns default-deny metadata policy before metrics/decision helpers can run.
- [ ] Slice 5 owns SM-03/SM-04 evaluation harness behavior.

### 📋 S — Tactical Plan

- [ ] Every implementation step references a specific file path.
- [ ] New files and modified files are clearly distinguished.
- [ ] `plan.md` includes a machine-readable `task_graph` block.
- [ ] Task graph dependencies match `outline.md` slice dependencies.
- [ ] Rollback strategy preserves no-op behavior when LangSmith is disabled.
- [ ] Plan does not require production code outside `living-adr` implementation paths.

### 🧹 P — Fresh Context

- [ ] Context reset points are identified after Slice 2 and before Slice 5.
- [ ] Each slice lists key files needed in context.
- [ ] Shared state to carry across slices is explicit: port method names, default-deny policy, repository scope, SM-01..SM-05 mapping.
- [ ] No slice assumes live LangSmith credentials for tests.

### 📝 Y — Task Yield

- [ ] Tasks are organized by user story.
- [ ] Every task maps to a `TASK-###` id in `plan.md`.
- [ ] Every task is completable in less than 2 hours or is split further.
- [ ] Test tasks exist for each functional behavior.
- [ ] Execution order respects dependencies.
- [ ] Parallel opportunities list only tasks with no shared writes.

### 🧪 No Horizontal Slicing (L3)

- [ ] Adapter behavior tests and implementation stay in Slice 1.
- [ ] Redaction tests and implementation stay in Slice 2.
- [ ] Metric helper tests and implementation stay in Slice 3.
- [ ] Decision/mutation tests and implementation stay in Slice 4.
- [ ] Evaluation fixture/runner tests and implementation stay in Slice 5.

## Feature-Specific Quality Gates

### Metadata-only traces and raw export controls

- [ ] Raw diffs are not exported to LangSmith by default.
- [ ] Full prompt bodies are not exported to LangSmith by default.
- [ ] Full provisional ADR drafts are not exported to LangSmith by default.
- [ ] Reviewer comments are not exported to LangSmith by default.
- [ ] Retrieved context/code snippets are not exported to LangSmith by default.
- [ ] Secrets and personal data are redacted or rejected before export.
- [ ] Opt-in raw export requires explicit debug config and remains denied for sensitive repositories.
- [ ] Redaction diagnostics contain reason codes and safe identifiers only.

### Metrics and success metrics

- [ ] **SM-01:** Draft acceptance/rejection/deferral outcome counters are emitted and tested.
- [ ] **SM-02:** PR-to-draft and per-stage latency metadata are emitted and tested.
- [ ] **SM-03:** Retrieval relevance evaluation emits per-query and aggregate regression signals.
- [ ] **SM-04:** Architecture question coverage evaluation emits answerable/unanswerable coverage results.
- [ ] **SM-05:** Unauthorized mutation attempts and successful approved mutations are emitted and tested.
- [ ] Token-count metrics emit numeric prompt/completion/total counts only.

### Port and dependency boundaries

- [ ] Feature 013 does not redefine the feature 002 `Observability` port.
- [ ] Application modules call only the core port or helper functions; they do not import LangSmith directly.
- [ ] LangSmith SDK usage is isolated to `src\living_adr\observability`.
- [ ] Observability failures do not break workflow, HITL, graph, or MCP user flows.
- [ ] Tests use fake LangSmith clients and do not require network access.

### Evaluation harness

- [ ] Held-out query fixture format is versioned.
- [ ] Drafting fixture format is versioned.
- [ ] Retrieval eval checks expected ADR/rationale references and missing citation cases.
- [ ] Drafting eval checks evidence citations, alternatives, consequences, and provisional-rationale labeling.
- [ ] Fixtures include at least one edge/rejected example to reduce overfitting risk.
- [ ] Output is machine-readable and suitable for CI/local review.
- [ ] Metric improvements are documented as regression signals, not proof of truth.

## Pre-Implementation Checks

- [ ] `spec.md`, `research.md`, `intent.md`, `outline.md`, `plan.md`, `tasks.md`, `checklist.md`, and `implementation-manifest.yaml` are complete and consistent.
- [ ] `implementation-manifest.yaml` slice count matches `outline.md`.
- [ ] Dependency on feature 002 is recorded and bounded to the existing `Observability` port.
- [ ] No unresolved open question blocks implementation start.
- [ ] No repo-wide feature branches are created during planning.

## Implementation Checks (per task)

- [ ] Task matches `plan.md` and `tasks.md`; no scope creep.
- [ ] Tests are written before or alongside implementation.
- [ ] No unrelated production behavior is changed.
- [ ] Code follows port/adapters pattern from architecture and feature 002.
- [ ] Checkpoint criteria from `outline.md` are met.
- [ ] Metadata exported by the task passes redaction/default-deny tests.
