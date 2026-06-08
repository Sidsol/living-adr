# Architecture Intent: tracked-repository-configuration

## Current State

LivingADR is greenfield. The authoritative architecture defines a single Python repository `living-adr` with shared `core` modules and two deployables, `workflow-service` and `mcp-context-server` (`..\..\architecture.md#repositories`, `..\..\architecture.md#deployment`). The data model already names `RepositoryIdentity` and `RepositoryConfig` as foundational contracts (`..\..\architecture.md#data-model`). Cross-cutting concerns require `living-adr.config.yaml`, `LIVING_ADR_CONFIG`, startup validation, no secrets in repository config, explicit external LLM policy, and restart-required lifecycle semantics (`..\..\architecture.md#cross-cutting`). Service boundaries assign core domain types and `Observability` to `core` (`..\..\architecture.md#service-boundaries`).

No production implementation exists yet, so this feature defines the seam rather than retrofitting existing code.

## Desired State

After this feature, both deployables have a shared typed configuration loader. Startup resolves the config path, parses YAML, validates repository identities/configuration, rejects invalid config with clear diagnostics, and exposes immutable configuration to downstream components. Publication policy and external LLM egress decisions are typed. Hot reload is intentionally absent; config changes require restarting both processes.

The feature also defines a thin `Observability` core port and no-op implementation. Later features instrument against this port; feature 013 replaces the no-op with LangSmith without forcing direct LangSmith dependencies into workflow, MCP, GitHub, HITL, graph, or drafting code.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Repository identity | Defined in `..\..\architecture.md#data-model`; no code yet | Typed `RepositoryIdentity` with canonical key and uniqueness validation | Create core model and validators |
| Repository config | Schema sketch in `..\..\architecture.md#cross-cutting` | Typed list of `RepositoryConfig` entries from YAML | Create schema, YAML loader, list validation |
| Startup behavior | Deployment expects two local processes | Both deployables fail fast on invalid config | Add app/entrypoint startup integration plan |
| Publication policy | Architecture enum values listed | Parsed enum with target branch/path validation | Add enum and cross-field validation |
| External LLM policy | Architecture requires per-repo allow/deny | Explicit boolean available to future Claude adapter | Add required config field and accessors |
| Lifecycle | Hot reload out of scope in architecture | Restart-required semantics documented and tested | Avoid watchers/reload APIs; snapshot config on startup |
| Observability | Tech stack chooses LangSmith wrapper; port assigned to feature 002 | Core `Observability` contract plus `NoOpObservability` | Define minimal methods and no-op behavior |
| Secrets boundary | Secrets in env/vault per `..\..\architecture.md#cross-cutting` | Repository config contains no secrets | Validate schema avoids secret fields |

## Architecture Options

### Option A: Direct YAML dictionaries consumed by services

**Approach:** Load YAML at each app boundary and pass dictionaries to consumers.

- ✅ Pros: Lowest initial code volume; easy to prototype.
- ❌ Cons: Duplicates parsing, weak validation, stringly typed policies, encourages downstream special cases and secret leakage.
- 🔧 Effort: Low.

### Option B: Pydantic core config models with shared loader (selected)

**Approach:** Define `RepositoryIdentity`, `RepositoryConfig`, `PublicationPolicy`, `LivingADRConfig`, and loader/startup diagnostics in core/app bootstrap. YAML is parsed once into typed models; consumers receive typed config.

- ✅ Pros: Strong validation, clear startup errors, reusable across both deployables, aligns with Pydantic/settings stack, supports N>=1 uniformly, prevents direct YAML coupling.
- ❌ Cons: Slightly more up-front structure; must avoid over-validating live GitHub state before feature 014.
- 🔧 Effort: Medium.

### Option C: Full dynamic configuration service with watchers

**Approach:** Implement a runtime config manager with file watchers, reload callbacks, and cross-process change propagation.

- ✅ Pros: Better operator ergonomics for future multi-repo changes.
- ❌ Cons: Violates PoC restart-required scope, introduces concurrency hazards across workflow/MCP processes, complicates tests and readiness.
- 🔧 Effort: High.

## Selected Approach

**Option B: Pydantic core config models with shared loader.**

Rationale: This option best matches `..\..\architecture.md#cross-cutting` and `..\..\architecture.md#deployment`: config is read at startup, invalid config fails readiness, and changing tracked repos requires restart. It gives downstream features a stable core contract without prematurely building hot reload or live GitHub validation. It also lets the no-op `Observability` port live alongside other core ports from `..\..\architecture.md#service-boundaries`.

## Config Seam Contract

The implementation should expose a small, stable seam:

- `RepositoryIdentity`: provider-neutral scope key used by SCM, graph, MCP, workflow, audit, and observability metadata.
- `RepositoryConfig`: repository onboarding and policy record; no secrets.
- `LivingADRConfig`: top-level collection with `repositories: list[RepositoryConfig]` and lookup helpers by canonical key.
- `load_living_adr_config(path: Path | None = None) -> LivingADRConfig`: resolves `LIVING_ADR_CONFIG` when no explicit path is supplied.
- `ConfigStartupError`: wraps validation and I/O failures with operator-readable messages for app startup.

The seam must avoid an `if single_repo:` branch. The PoC one-repo case is represented as a list of length one.

## No-Op Observability Port Contract

The port should be thin, metadata-first, and dependency-free in `core`:

- `record_event(name: str, metadata: Mapping[str, object] | None = None) -> None`
- `increment_counter(name: str, value: int = 1, metadata: Mapping[str, object] | None = None) -> None`
- `start_span(name: str, metadata: Mapping[str, object] | None = None) -> ContextManager[ObservationSpan]`

`NoOpObservability` should implement the contract without network calls, storage, or exceptions for normal metadata inputs. The contract documentation should state that raw diffs, full prompts, provisional ADR drafts, reviewer comments, secrets, and retrieved context are default-deny payloads per `..\..\architecture.md#cross-cutting`; feature 013 owns LangSmith export/redaction.

## Module Surface Analysis

| Module | Inputs | Callers | Deletion test | Isolated-test candidate |
|---|---:|---|---|---|
| `src\living_adr\core\config.py` | YAML dicts, env path, filesystem path | app startup, tests, future adapters | Deleting breaks repository scoping for all deployables | Yes — pure validation and loading with temp project fixtures |
| `src\living_adr\core\models.py` or `core\repository.py` | field values | config, SCM, graph, MCP | Deleting forces duplicate identity definitions | Yes — pure value-object validation |
| `src\living_adr\core\observability.py` | event/span names, metadata | all later features | Deleting makes later instrumentation depend on LangSmith directly | Yes — no-op behavior and context manager tests |
| `src\living_adr\apps\workflow_service\startup.py` | `LivingADRConfig`, settings | workflow entrypoint | Deleting allows invalid config to pass readiness | Partially — use fake app/settings, no network |
| `src\living_adr\apps\mcp_context_server\startup.py` | `LivingADRConfig`, settings | MCP entrypoint | Deleting removes repository filtering precondition | Partially — use fake app/settings, no MCP network |
| `tests\core\test_config.py` | fixture YAML strings | pytest | Deleting loses validation matrix | n/a |
| `tests\core\test_observability.py` | no-op instance | pytest | Deleting risks port regression | n/a |
| `tests\apps\test_startup_config.py` | invalid config fixtures | pytest | Deleting risks partial startup | n/a |

## Anti-Patterns to Avoid

- **Hardcoded PoC repository:** tempting for speed, but violates configuration-only onboarding and blocks feature 014.
- **Single-repo branch:** `if len(repositories) == 1` logic will hide multi-repo bugs; iterate the list uniformly.
- **Stringly typed publication policy:** raw strings will create inconsistent publish-back behavior; use an enum.
- **Implicit external LLM allow:** omitted fields must not silently permit Claude egress.
- **Live GitHub validation in core loader:** installation status checks require credentials/rate limits and belong in onboarding diagnostics, not pure config parsing.
- **LangSmith import in core port:** feature 002 should not couple all downstream features to LangSmith; feature 013 supplies the adapter.
- **Hot-reload watcher:** violates restart-required PoC semantics and creates cross-process consistency hazards.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add core config models/loader, no-op observability port, startup integration, tests, sample config documentation | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Over-validating GitHub installation availability in startup blocks local tests | Medium | Medium | Limit feature 002 to local syntactic validation; leave live checks to feature 014 seam. |
| Config shape leaks GitHub-only assumptions into core | Medium | High | Keep `provider` explicit and `RepositoryIdentity` provider-neutral; isolate GitHub installation fields as provider config or clearly GitHub-prefixed field. |
| External LLM policy defaults unsafe | Medium | High | Require explicit boolean and test both allow and deny. |
| Observability port too broad before LangSmith design | Medium | Medium | Keep minimal event/counter/span interface; feature 013 can extend through adapter-compatible additions. |
| Invalid config errors are too opaque for operators | Medium | Medium | Wrap Pydantic validation into field-path messages with repository identity context where available. |
| Restart semantics accidentally become reload semantics through settings access | Low | Medium | Load once at startup and inject snapshot; tests modify file after load and assert existing config unchanged. |
