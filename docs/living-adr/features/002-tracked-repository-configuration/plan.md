# Implementation Plan: tracked-repository-configuration

## Technical Context

- Language/Framework: Python 3.12, FastAPI app startup/lifespan for workflow service, Python MCP stdio entrypoint for context server.
- Key Dependencies: `pydantic`, `pydantic-settings`, YAML parser such as PyYAML if not already scaffolded, `python-dotenv` for env loading.
- Test Framework: pytest.
- Build System: uv with `pyproject.toml`; lint/format via Ruff.
- Architecture anchors: `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#repositories`, `..\..\architecture.md#deployment`.

## Project Structure

```text
living-adr\
├── living-adr.config.example.yaml          ← CREATE: sample non-secret repository config
├── pyproject.toml                          ← MODIFY: add YAML parser dependency if missing
├── src\living_adr\
│   ├── core\
│   │   ├── __init__.py                     ← MODIFY: export stable config/observability contracts if project style does this
│   │   ├── repository.py                   ← CREATE: RepositoryIdentity value object
│   │   ├── config.py                       ← CREATE: Pydantic config models and policy helpers
│   │   ├── config_loader.py                ← CREATE: path resolution, YAML parse, startup error formatting
│   │   └── observability.py                ← CREATE: Observability port and NoOpObservability
│   └── apps\
│       ├── workflow_service\
│       │   └── startup.py                  ← CREATE/MODIFY: load config at startup and fail readiness on invalid config
│       └── mcp_context_server\
│           └── startup.py                  ← CREATE/MODIFY: load config at startup and fail before serving tools
└── tests\
    ├── core\
    │   ├── test_config_models.py           ← CREATE
    │   ├── test_config_loader.py           ← CREATE
    │   ├── test_config_policy.py           ← CREATE
    │   ├── test_config_lifecycle.py        ← CREATE
    │   └── test_observability.py           ← CREATE
    └── apps\
        └── test_startup_config.py          ← CREATE
```

## Implementation Phases

### Phase 1: Core repository config models

#### Step 1.1: Add repository identity tests (RED)

- **Task ID:** TASK-001
- **File:** `tests\core\test_config_models.py`
- **Action:** Create
- **Changes:** Add tests for valid `RepositoryIdentity`, canonical key generation, missing required fields, and invalid empty/unsafe values.

#### Step 1.2: Implement repository identity model (GREEN)

- **Task ID:** TASK-002
- **File:** `src\living_adr\core\repository.py`
- **Action:** Create
- **Changes:** Add Pydantic or dataclass value object with `host`, `owner`, `repo`, `repo_id`, canonical key property, and validation.

#### Step 1.3: Add config collection tests (RED)

- **Task ID:** TASK-003
- **File:** `tests\core\test_config_models.py`
- **Action:** Modify
- **Changes:** Add tests for `LivingADRConfig.repositories`, `N>=1`, duplicate identity rejection, and no secret-bearing fields.

#### Step 1.4: Implement config models (GREEN)

- **Task ID:** TASK-004
- **File:** `src\living_adr\core\config.py`
- **Action:** Create
- **Changes:** Add `RepositoryConfig`, `LivingADRConfig`, validation for non-empty list, duplicate canonical keys, provider, GitHub installation id, branches, and ADR path template basics.

#### Step 1.5: Export core contracts

- **Task ID:** TASK-005
- **File:** `src\living_adr\core\__init__.py`
- **Action:** Modify
- **Changes:** Export `RepositoryIdentity`, `RepositoryConfig`, `LivingADRConfig`, and `PublicationPolicy` if existing package conventions expose core contracts here.

### Phase 2: YAML loader and startup diagnostics

#### Step 2.1: Add loader tests (RED)

- **Task ID:** TASK-006
- **File:** `tests\core\test_config_loader.py`
- **Action:** Create
- **Changes:** Test default path resolution, `LIVING_ADR_CONFIG` override, missing file, invalid YAML, and Pydantic validation error formatting.

#### Step 2.2: Implement config loader (GREEN)

- **Task ID:** TASK-007
- **File:** `src\living_adr\core\config_loader.py`
- **Action:** Create
- **Changes:** Implement `load_living_adr_config`, config path resolution, YAML parsing, conversion to `LivingADRConfig`, and `ConfigStartupError` with actionable messages.

#### Step 2.3: Add startup integration tests (RED)

- **Task ID:** TASK-008
- **File:** `tests\apps\test_startup_config.py`
- **Action:** Create
- **Changes:** Use fake config paths to assert workflow and MCP startup helpers return/load config on valid input and fail readiness on invalid input.

#### Step 2.4: Wire workflow startup (GREEN)

- **Task ID:** TASK-009
- **File:** `src\living_adr\apps\workflow_service\startup.py`
- **Action:** Create/Modify
- **Changes:** Load config once during startup/lifespan, attach validated config to app state or dependency container, and translate `ConfigStartupError` into process startup failure.

#### Step 2.5: Wire MCP startup (GREEN)

- **Task ID:** TASK-010
- **File:** `src\living_adr\apps\mcp_context_server\startup.py`
- **Action:** Create/Modify
- **Changes:** Load config once before registering/serving MCP resources/tools and fail startup on invalid config.

### Phase 3: Publication and external LLM policy parsing

#### Step 3.1: Add publication policy tests (RED)

- **Task ID:** TASK-011
- **File:** `tests\core\test_config_policy.py`
- **Action:** Create
- **Changes:** Test all valid `adr_publication_policy` values, unknown policy rejection, publish-to-GitHub target branch/path requirements, and relative path template safety.

#### Step 3.2: Implement publication policy enum and validators (GREEN)

- **Task ID:** TASK-012
- **File:** `src\living_adr\core\config.py`
- **Action:** Modify
- **Changes:** Add `PublicationPolicy` enum, `publishes_to_github` helper, and cross-field validation for target branch/path when publishing to GitHub.

#### Step 3.3: Add external LLM policy tests (RED)

- **Task ID:** TASK-013
- **File:** `tests\core\test_config_policy.py`
- **Action:** Modify
- **Changes:** Test explicit `external_llm_allowed: true`, explicit false, omitted value behavior, and repository lookup for LLM egress decision.

#### Step 3.4: Implement external LLM policy helpers (GREEN)

- **Task ID:** TASK-014
- **File:** `src\living_adr\core\config.py`
- **Action:** Modify
- **Changes:** Require/parse `external_llm_allowed: bool` and add lookup/helper methods that future Claude adapter can call.

### Phase 4: Restart-required lifecycle semantics

#### Step 4.1: Add lifecycle snapshot tests (RED)

- **Task ID:** TASK-015
- **File:** `tests\core\test_config_lifecycle.py`
- **Action:** Create
- **Changes:** Load config from a file, mutate file contents, and assert the existing in-memory `LivingADRConfig` remains unchanged until loader is called again.

#### Step 4.2: Ensure startup uses injected snapshot (GREEN)

- **Task ID:** TASK-016
- **Files:** `src\living_adr\apps\workflow_service\startup.py`, `src\living_adr\apps\mcp_context_server\startup.py`
- **Action:** Modify
- **Changes:** Ensure startup stores a validated config snapshot and downstream request/tool handlers receive that snapshot rather than re-reading files.

#### Step 4.3: Add sample config and restart note

- **Task ID:** TASK-017
- **File:** `living-adr.config.example.yaml`
- **Action:** Create
- **Changes:** Add non-secret example config and comments stating config changes require restarting both `living-adr-workflow` and `living-adr-mcp`; no hot reload in PoC.

### Phase 5: No-op Observability core port

#### Step 5.1: Add no-op observability tests (RED)

- **Task ID:** TASK-018
- **File:** `tests\core\test_observability.py`
- **Action:** Create
- **Changes:** Test `record_event`, `increment_counter`, and `start_span` success/exception paths with no network/storage side effects and no LangSmith import requirement.

#### Step 5.2: Implement observability port and no-op (GREEN)

- **Task ID:** TASK-019
- **File:** `src\living_adr\core\observability.py`
- **Action:** Create
- **Changes:** Define `Observability` protocol/interface, `ObservationSpan`, and `NoOpObservability`; include metadata-only/default-deny raw export docstrings.

#### Step 5.3: Export observability contract

- **Task ID:** TASK-020
- **File:** `src\living_adr\core\__init__.py`
- **Action:** Modify
- **Changes:** Export `Observability`, `ObservationSpan`, and `NoOpObservability` if package conventions expose core ports here.

### Phase 6: Verification

#### Step 6.1: Run unit tests

- **Task ID:** TASK-021
- **Files:** `tests\core\test_config_models.py`, `tests\core\test_config_loader.py`, `tests\core\test_config_policy.py`, `tests\core\test_config_lifecycle.py`, `tests\core\test_observability.py`, `tests\apps\test_startup_config.py`
- **Action:** Verify
- **Changes:** Run the existing pytest command and fix only failures caused by this feature.

#### Step 6.2: Run lint checks

- **Task ID:** TASK-022
- **File:** `pyproject.toml`
- **Action:** Verify
- **Changes:** Run the existing Ruff command and fix only issues caused by this feature.

#### Step 6.3: Confirm observability boundary

- **Task ID:** TASK-023
- **File:** `src\living_adr\core\observability.py`
- **Action:** Verify
- **Changes:** Confirm the core observability module imports no LangSmith package and performs no network I/O.

## Complexity Tracking

| Phase | Files Changed | New Files | Estimated Effort | Risk |
|---|---:|---:|---|---|
| Phase 1 | 1 | 3 | Medium | Medium |
| Phase 2 | 2 | 3 | Medium | Medium |
| Phase 3 | 1 | 1 | Low | High policy sensitivity |
| Phase 4 | 2 | 2 | Low | Low |
| Phase 5 | 1 | 2 | Low | Medium boundary sensitivity |
| Phase 6 | 0 | 0 | Low | Low |

## Dependencies & Prerequisites

- Project scaffold from `..\..\architecture.md#tech-stack` exists at `C:\repos\living-adr`.
- If no YAML parser is available in scaffold, add a pinned parser dependency through uv and lock it.
- No live GitHub, Claude, LangSmith, graph, SQLite, or MCP server connection is required for this feature's tests.
- Repository config file must not include secrets; use `.env.local`/environment for runtime secrets.

## Rollback Strategy

- Phase 1 rollback: remove config model files and tests; downstream features should not yet depend on them.
- Phase 2 rollback: remove startup wiring and loader; services return to prior scaffold startup behavior.
- Phase 3 rollback: remove policy helpers and validators, but do not leave raw string policy partially accepted.
- Phase 4 rollback: remove sample config and lifecycle tests; retain startup fail-fast if already accepted.
- Phase 5 rollback: remove no-op observability exports only if no downstream feature has imported them; otherwise introduce compatibility shim.

## Machine-Readable Task Graph

```yaml
task_graph:
  - id: TASK-001
    slice: 1
    story: US-2
    depends_on: []
    parallelizable_with: []
    files: [tests\core\test_config_models.py]
  - id: TASK-002
    slice: 1
    story: US-2
    depends_on: [TASK-001]
    parallelizable_with: []
    files: [src\living_adr\core\repository.py]
  - id: TASK-003
    slice: 1
    story: US-1
    depends_on: [TASK-002]
    parallelizable_with: []
    files: [tests\core\test_config_models.py]
  - id: TASK-004
    slice: 1
    story: US-1
    depends_on: [TASK-003]
    parallelizable_with: []
    files: [src\living_adr\core\config.py]
  - id: TASK-005
    slice: 1
    story: US-1
    depends_on: [TASK-004]
    parallelizable_with: []
    files: [src\living_adr\core\__init__.py]
  - id: TASK-006
    slice: 2
    story: US-1
    depends_on: [TASK-005]
    parallelizable_with: []
    files: [tests\core\test_config_loader.py]
  - id: TASK-007
    slice: 2
    story: US-1
    depends_on: [TASK-006]
    parallelizable_with: []
    files: [src\living_adr\core\config_loader.py]
  - id: TASK-008
    slice: 2
    story: US-4
    depends_on: [TASK-007]
    parallelizable_with: []
    files: [tests\apps\test_startup_config.py]
  - id: TASK-009
    slice: 2
    story: US-4
    depends_on: [TASK-008]
    parallelizable_with: []
    files: [src\living_adr\apps\workflow_service\startup.py]
  - id: TASK-010
    slice: 2
    story: US-4
    depends_on: [TASK-008]
    parallelizable_with: []
    files: [src\living_adr\apps\mcp_context_server\startup.py]
  - id: TASK-011
    slice: 3
    story: US-3
    depends_on: [TASK-005]
    parallelizable_with: [TASK-006]
    files: [tests\core\test_config_policy.py]
  - id: TASK-012
    slice: 3
    story: US-3
    depends_on: [TASK-011]
    parallelizable_with: []
    files: [src\living_adr\core\config.py]
  - id: TASK-013
    slice: 3
    story: US-3
    depends_on: [TASK-012]
    parallelizable_with: []
    files: [tests\core\test_config_policy.py]
  - id: TASK-014
    slice: 3
    story: US-3
    depends_on: [TASK-013]
    parallelizable_with: []
    files: [src\living_adr\core\config.py]
  - id: TASK-015
    slice: 4
    story: US-4
    depends_on: [TASK-010, TASK-014]
    parallelizable_with: []
    files: [tests\core\test_config_lifecycle.py]
  - id: TASK-016
    slice: 4
    story: US-4
    depends_on: [TASK-015]
    parallelizable_with: []
    files: [src\living_adr\apps\workflow_service\startup.py, src\living_adr\apps\mcp_context_server\startup.py]
  - id: TASK-017
    slice: 4
    story: US-4
    depends_on: [TASK-016]
    parallelizable_with: []
    files: [living-adr.config.example.yaml]
  - id: TASK-018
    slice: 5
    story: US-5
    depends_on: [TASK-005]
    parallelizable_with: [TASK-006, TASK-011]
    files: [tests\core\test_observability.py]
  - id: TASK-019
    slice: 5
    story: US-5
    depends_on: [TASK-018]
    parallelizable_with: []
    files: [src\living_adr\core\observability.py]
  - id: TASK-020
    slice: 5
    story: US-5
    depends_on: [TASK-019]
    parallelizable_with: []
    files: [src\living_adr\core\__init__.py]
  - id: TASK-021
    slice: verification
    story: Verification
    depends_on: [TASK-017, TASK-020]
    parallelizable_with: [TASK-022, TASK-023]
    files: [tests\core\test_config_models.py, tests\core\test_config_loader.py, tests\core\test_config_policy.py, tests\core\test_config_lifecycle.py, tests\core\test_observability.py, tests\apps\test_startup_config.py]
  - id: TASK-022
    slice: verification
    story: Verification
    depends_on: [TASK-017, TASK-020]
    parallelizable_with: [TASK-021, TASK-023]
    files: [pyproject.toml]
  - id: TASK-023
    slice: verification
    story: Verification
    depends_on: [TASK-019]
    parallelizable_with: [TASK-021, TASK-022]
    files: [src\living_adr\core\observability.py]
```
