# Implementation Outline: tracked-repository-configuration

## Slice Strategy

The feature is decomposed into five vertical slices that each produce testable behavior and preserve the configuration seam before downstream features depend on it. The order starts with pure core models, then loading/startup, then policy accessors, then lifecycle semantics, and finally the no-op observability port. This keeps high-risk policy and startup behavior testable without requiring GitHub, Claude, LangSmith, graph storage, or MCP runtime.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| 1 | Core repository config models | US-1, US-2 | M | — | false | HITL | Establishes shared source-of-truth contracts consumed by all later features and needs review for scope/identity semantics. |
| 2 | YAML loader and startup diagnostics | US-1, US-4 | M | 1 | false | HITL | Startup failure behavior affects both deployables and readiness semantics. |
| 3 | Publication and external LLM policy parsing | US-3 | S | 1 | true | HITL | Policy decisions govern GitHub writes and external data egress, requiring human review. |
| 4 | Restart-required lifecycle semantics | US-4 | S | 2, 3 | false | AFK | Purely verifies absence of hot reload and startup snapshot behavior once loader/policies exist. |
| 5 | No-op Observability core port | US-5 | S | 1 | true | HITL | Defines an instrumentation boundary for later features and must preserve default-deny trace semantics. |

## Slices

### Slice 1: Core repository config models

**Scope:** Define typed domain/config models and validation for repository identity uniqueness and required fields.

**User Stories:** US-1, US-2

**Automation:** HITL

**Automation Reason:** Establishes contracts downstream features depend on for repository scoping and multi-repo correctness.

**Deliverables:**

- `src\living_adr\core\config.py` containing `LivingADRConfig`, `RepositoryConfig`, `PublicationPolicy`, and local validators.
- `src\living_adr\core\repository.py` or equivalent containing `RepositoryIdentity` value object.
- `tests\core\test_config_models.py` with valid, invalid, duplicate, and `N>=1` cases.

**Checkpoint Criteria:**

- [ ] A one-entry repository list validates without a single-repo branch.
- [ ] Duplicate canonical repository identities fail validation.
- [ ] Missing identity fields fail with field-specific messages.
- [ ] No model field accepts secret values such as API keys or private keys.

**Context Notes:**

- Key files: `src\living_adr\core\config.py`, `src\living_adr\core\repository.py`, `tests\core\test_config_models.py`.
- Dependencies: project scaffold exists.
- Estimated complexity: Medium.

### Slice 2: YAML loader and startup diagnostics

**Scope:** Load config from default path or `LIVING_ADR_CONFIG`, convert parser/Pydantic errors into startup diagnostics, and wire both deployables to fail fast.

**User Stories:** US-1, US-4

**Automation:** HITL

**Automation Reason:** Startup readiness and error reporting are operator-visible safety boundaries.

**Deliverables:**

- `src\living_adr\core\config_loader.py` with path resolution, YAML parsing, and `ConfigStartupError`.
- `src\living_adr\apps\workflow_service\startup.py` consuming loader before readiness.
- `src\living_adr\apps\mcp_context_server\startup.py` consuming loader before serving MCP tools.
- `tests\core\test_config_loader.py` and `tests\apps\test_startup_config.py`.

**Checkpoint Criteria:**

- [ ] Default path is used when `LIVING_ADR_CONFIG` is absent.
- [ ] Override path is used when `LIVING_ADR_CONFIG` is set.
- [ ] Invalid YAML or model validation errors produce clear startup diagnostics.
- [ ] Both deployables refuse readiness on invalid config.

**Context Notes:**

- Key files: loader, startup modules, startup tests.
- Dependencies: Slice 1 models.
- Estimated complexity: Medium.

### Slice 3: Publication and external LLM policy parsing

**Scope:** Parse and validate `adr_publication_policy`, target branch/path semantics, and explicit `external_llm_allowed` for later GitHub publish-back and Claude egress enforcement.

**User Stories:** US-3

**Automation:** HITL

**Automation Reason:** This slice defines governance and data-egress policy semantics that should not be silently inferred.

**Deliverables:**

- `PublicationPolicy` enum in `src\living_adr\core\config.py`.
- Policy helper methods such as `publishes_to_github` and `allows_external_llm(repository)`.
- Validation tests covering all policy values and deny/allow flags.

**Checkpoint Criteria:**

- [ ] All three architecture-approved publication policies parse successfully.
- [ ] Unknown publication policy fails validation.
- [ ] Publish-to-GitHub policies require valid target branch and relative ADR path template.
- [ ] External LLM allow and deny states are both explicit and test-covered.

**Context Notes:**

- Key files: `src\living_adr\core\config.py`, `tests\core\test_config_policy.py`.
- Dependencies: Slice 1 models.
- Estimated complexity: Low.

### Slice 4: Restart-required lifecycle semantics

**Scope:** Ensure services load a startup snapshot and do not watch or reload config changes during runtime. Document operator restart requirement.

**User Stories:** US-4

**Automation:** AFK

**Automation Reason:** Once startup loading exists, this is additive test/documentation work with no new external boundary.

**Deliverables:**

- Tests proving loaded config remains unchanged after file mutation.
- Operator note in sample config or README section stating both `living-adr-workflow` and `living-adr-mcp` require restart after config changes.
- Startup code structured to inject config snapshot rather than re-reading per request/tool call.

**Checkpoint Criteria:**

- [ ] Tests show no hot reload after file changes.
- [ ] No file watcher, background reload task, or per-request config parse is introduced.
- [ ] Documentation states config changes require restarting both deployables.

**Context Notes:**

- Key files: `tests\core\test_config_lifecycle.py`, startup modules, docs/sample config.
- Dependencies: Slices 2 and 3.
- Estimated complexity: Low.

### Slice 5: No-op Observability core port

**Scope:** Define a thin `Observability` interface and `NoOpObservability` implementation in core with metadata-only method contracts.

**User Stories:** US-5

**Automation:** HITL

**Automation Reason:** Creates the cross-feature instrumentation boundary and must avoid leaking raw trace content before feature 013.

**Deliverables:**

- `src\living_adr\core\observability.py` with port, span context manager, and no-op implementation.
- `tests\core\test_observability.py` proving no-op event/counter/span calls succeed without side effects.
- Contract docstrings stating default-deny raw export categories.

**Checkpoint Criteria:**

- [ ] `NoOpObservability.record_event`, `increment_counter`, and `start_span` are safe with metadata-only payloads.
- [ ] Span context manager exits cleanly on success and exception paths.
- [ ] Core observability module imports no LangSmith package.
- [ ] Tests assert raw export restrictions are documented in the contract.

**Context Notes:**

- Key files: `src\living_adr\core\observability.py`, `tests\core\test_observability.py`.
- Dependencies: Slice 1 for core package conventions.
- Estimated complexity: Low.

## Slice Dependency Graph

```text
Slice 1 ──→ Slice 2 ──→ Slice 4
Slice 1 ──→ Slice 3 ──→ Slice 4
Slice 1 ──→ Slice 5
```

## Slice Dependency Graph (Machine-Readable)

```yaml
slices:
  - id: 1
    name: Core repository config models
    depends_on: []
    parallelizable: false
    automation: HITL
    automation_reason: "Establishes shared source-of-truth contracts consumed by all later features and needs review for scope/identity semantics."
    checkpoint_criteria_count: 4
  - id: 2
    name: YAML loader and startup diagnostics
    depends_on: [1]
    parallelizable: false
    automation: HITL
    automation_reason: "Startup failure behavior affects both deployables and readiness semantics."
    checkpoint_criteria_count: 4
  - id: 3
    name: Publication and external LLM policy parsing
    depends_on: [1]
    parallelizable: true
    automation: HITL
    automation_reason: "Policy decisions govern GitHub writes and external data egress, requiring human review."
    checkpoint_criteria_count: 4
  - id: 4
    name: Restart-required lifecycle semantics
    depends_on: [2, 3]
    parallelizable: false
    automation: AFK
    automation_reason: "Purely verifies absence of hot reload and startup snapshot behavior once loader/policies exist."
    checkpoint_criteria_count: 3
  - id: 5
    name: No-op Observability core port
    depends_on: [1]
    parallelizable: true
    automation: HITL
    automation_reason: "Defines an instrumentation boundary for later features and must preserve default-deny trace semantics."
    checkpoint_criteria_count: 4
```

> **Note:** `parallelizable` is a static planning-time hint, not a runtime guarantee. `crispy-implement` re-evaluates parallelizability dynamically based on dependency satisfaction and file-set conflict detection at execution time.

## Context Management

- Maximum files open per slice: 5 implementation files plus matching tests.
- Recommended context window reset points: after Slice 1 and after Slice 3; Slice 5 can run in a fresh context with only core package conventions and observability contract.
- State that must carry across slices: canonical `RepositoryIdentity` format, publication policy enum values, no-secrets rule, restart-required constraint, and no LangSmith dependency in core.

## Verification Strategy

Complete verification should run the repository's existing checks after scaffold exists: `uv run pytest`, `uv run ruff check`, and any app startup tests. The feature is complete when valid config allows both deployable startup paths, invalid config blocks readiness, policy accessors return expected values, config snapshots do not hot-reload, and no-op observability tests pass without LangSmith.
