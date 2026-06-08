# Technical Research: tracked-repository-configuration

> Planning research grounded in inherited project artifacts. No production `living-adr` codebase exists under `C:\repos` yet, so this research documents the authoritative architecture and domain constraints that implementation must satisfy.

## Architecture Overview

LivingADR is planned as a single Python 3.12 repository, `living-adr`, containing shared `core` code plus two deployables: `workflow-service` and `mcp-context-server`. The architecture selects FastAPI/Uvicorn for service surfaces, LangGraph for workflow orchestration, LlamaIndex PropertyGraphIndex behind graph ports, Claude through the Anthropic SDK, the Python MCP SDK for read-only context delivery, SQLite WAL for PoC state, and LangSmith behind a thin `Observability` wrapper.

Configuration is a cross-cutting concern: `living-adr.config.yaml` is the source of truth for tracked repositories, loaded at startup by both deployables, and changed only by restart during the PoC. Repository identity is first-class in the data model and must scope domain records, SCM calls, graph nodes, graph queries, and MCP filtering.

## Source References

- `..\..\architecture.md#tech-stack`: Python 3.12, Pydantic settings, pytest, uv, FastAPI, MCP SDK, LangSmith wrapper.
- `..\..\architecture.md#repositories`: single local repo `living-adr` with shared `core`, `scm`, `graph`, `workflow`, `hitl`, `observability`, and app packages.
- `..\..\architecture.md#service-boundaries`: `core` owns `RepositoryIdentity`, ports, and `Observability`; downstream adapters depend on these types.
- `..\..\architecture.md#data-model`: `RepositoryIdentity` and `RepositoryConfig` shape and repository-scope rules.
- `..\..\architecture.md#cross-cutting`: config source, validation, secrets boundary, external LLM policy, default-deny observability export.
- `..\..\architecture.md#deployment`: local PoC runs workflow and MCP as two processes that both need startup config.
- `..\..\domain-research.md §7`: common failure modes FM-14, FM-15, FM-16, FM-17, FM-21, FM-23, FM-24.

## Configuration Format Research

### YAML source of truth

The architecture mandates `living-adr.config.yaml` with `LIVING_ADR_CONFIG` override. YAML is appropriate for operator-owned repository onboarding because it is readable, supports lists and nested repository entries, and aligns with related docs-as-code conventions such as Backstage `catalog-info.yaml` and ADR tool configuration. The implementation should parse YAML into typed Pydantic models rather than letting downstream services inspect dictionaries.

### Proposed schema skeleton

```yaml
repositories:
  - identity:
      host: github.com
      owner: example-owner
      repo: example-repo
      repo_id: "123456789"
    provider: github
    github_app_installation_id: 123456
    default_branch: main
    adr_target_branch: main
    adr_path_template: docs/adr/NNNN-{slug}.md
    adr_publication_policy: livingadr_only
    external_llm_allowed: true
    retention:
      trace_days: 30
    sampling:
      successful_runs: 1.0
```

### Pydantic/settings approach

The architecture includes `pydantic-settings==2.14.1` and `python-dotenv`. Recommended implementation is:

1. Use a small settings class for process-level paths and env flags, e.g. `LIVING_ADR_CONFIG`.
2. Load YAML bytes from the resolved config path.
3. Validate YAML content with Pydantic v2 models (`BaseModel`, `Field`, `field_validator`, `model_validator`).
4. Return immutable or mutation-discouraged config objects for dependency injection.
5. Format Pydantic `ValidationError` details into startup diagnostics.

This keeps secrets (`ANTHROPIC_API_KEY`, GitHub private key path, LangSmith key, UI token) in environment/settings while repository-scoped policy remains in YAML.

## Relevant Data Models

### RepositoryIdentity

Authoritative shape from architecture: `host/owner/repo` plus opaque provider `repo_id`. The canonical key should be derived from normalized `host`, `owner`, and `repo`; `repo_id` remains available for provider API calls and durable mapping.

Validation considerations:

- `host`, `owner`, `repo`, and `repo_id` are required and non-empty.
- Canonical key uniqueness is enforced across the full repositories list.
- Provider-specific host normalization should be minimal in PoC: trim whitespace, reject path separators/control characters, and preserve case policy deliberately.

### RepositoryConfig

Architecture fields: provider type, GitHub App installation id, default branch, ADR target branch, ADR path template, `adr_publication_policy`, and external LLM allow/deny. Optional per-repository retention/sampling overrides are mentioned in the schema sketch and should be retained as future-friendly optional nested config.

Validation considerations:

- `repositories` list must contain at least one entry.
- `github_app_installation_id` must be present for GitHub repositories and syntactically valid.
- Publish policies that write to GitHub require non-empty branch and path template.
- Path template should reject absolute paths, parent traversal, and paths outside the repository workspace.
- `external_llm_allowed` must be explicit; avoid implicit allow-by-omission.

### PublicationPolicy

Architecture enum values:

- `livingadr_only`
- `publish_to_github`
- `publish_to_github_and_livingadr`

This policy controls future feature 011 behavior and should be parsed as a typed enum rather than string comparisons.

### Observability

Architecture chooses LangSmith through a thin `Observability` wrapper, but feature 002 only establishes the core port and no-op implementation. The port must support metadata-only structured events/spans/counters without importing LangSmith. Feature 013 later supplies the LangSmith adapter.

Research implication: because FM-21 warns about sensitive trace leakage, the port contract should document that raw diffs, prompts, provisional drafts, reviewer comments, and retrieved context are not valid default metadata. No-op behavior should preserve caller ergonomics without producing side effects.

## Integration Points

| Integration | Type | Relevant to this feature | Notes |
|---|---|---|---|
| GitHub App installation | Future SCM adapter | Config stores installation id only | Live permission validation belongs mostly to feature 014. |
| Anthropic Claude | Future LLM adapter | `external_llm_allowed` controls egress eligibility | Deny must be explicit and queryable before drafting. |
| LangSmith | Future observability adapter | Feature 002 creates only the no-op port | Real implementation and instrumentation matrix are feature 013. |
| Workflow service | Startup consumer | Must fail fast on invalid config | FastAPI lifespan/startup hook can validate before readiness. |
| MCP context server | Startup consumer | Must load same config for repository filtering | Read-only server must not get write credentials. |
| Publish-back | Future GitHub adapter | Publication policy and target fields are parsed now | Direct commit vs PR remains a later open question. |

## Relevant Failure Modes

- **FM-14 Prompt/tool injection:** repository text is untrusted; config must make external LLM egress explicit and default-deny trace export later.
- **FM-15 MCP local-server trust failure / FM-16 MCP auth mismatch:** the MCP server should only receive repository-scoped read configuration and no mutation or SCM credentials through this feature.
- **FM-17 SCM event duplication, gaps, and replay complexity:** stable `RepositoryIdentity` enables idempotent event keys and manual replay in feature 003.
- **FM-21 Sensitive data in traces:** observability contract must distinguish metadata from raw prompts/diffs/drafts.
- **FM-23 Docs-as-code without review gates:** publication policy must not imply generated Markdown is authoritative before approval.
- **FM-24 Cross-SCM abstraction leaks:** config should identify provider while exposing normalized repository identity to core code.

## Testing Patterns Recommended

- Unit tests for model validation success/failure matrices.
- Parameterized tests for all publication policy enum values.
- Tests for duplicate identity detection across multiple repository entries.
- Tests for explicit `external_llm_allowed` true/false parsing.
- Tests proving config path override precedence.
- Startup tests using fake app factories to assert invalid config prevents readiness.
- No-op observability tests verifying event/span/counter methods are side-effect free.
- Restart semantics tests using a loader instance or application config snapshot: changing file contents after load does not mutate existing in-memory config.

## Technical Debt and Observations

- The project is greenfield; no existing production code constrains the module names beyond `architecture.md` package layout.
- Architecture references LangSmith in the tech stack but reviewer findings defer concrete instrumentation mapping to feature-level plans; feature 002 should avoid over-designing the LangSmith implementation and only establish the port.
- Architecture validation says startup refuses invalid GitHub App installation ids as not installed; live installation verification likely requires GitHub API credentials and is more appropriate for feature 014. Feature 002 should perform syntactic and local consistency validation, with a clear seam for later active checks.
- Open architecture question asks whether config should support templating or env interpolation; PoC should remain literal-only unless implementation has a strong reason otherwise.

## Key Patterns

- **Ports in core, adapters outside:** `RepositoryIdentity`, config models, and `Observability` belong in `src\living_adr\core`.
- **Repository scope everywhere:** all downstream ports accept or filter by `RepositoryIdentity`.
- **Startup fail-fast:** invalid config blocks deployable readiness rather than producing partial behavior.
- **No secrets in config:** config references installation ids and policies, while secrets are resolved from env/vault.
- **PoC one repo, model many repos:** `len(repositories) == 1` is valid input, not a special architecture path.
