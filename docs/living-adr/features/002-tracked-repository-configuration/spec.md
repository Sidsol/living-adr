# Feature Specification: tracked-repository-configuration

## Overview

Feature 002 establishes LivingADR's repository-configuration seam for the 1-repo PoC while treating `N >= 1` repositories uniformly. It defines loading and validation for `living-adr.config.yaml`, validates `RepositoryIdentity` and `RepositoryConfig`, surfaces invalid configuration as startup errors, parses ADR publication policy and external-LLM allow/deny flags, documents restart-required lifecycle semantics, and establishes the thin no-op `Observability` core port that later features instrument against.

This feature serves TH-07 Governance & Repository Onboarding and unlocks downstream GitHub ingestion, Claude egress policy enforcement, graph scoping, MCP filtering, publish-back, and LangSmith observability implementation.

## User Stories

### [US-1] Load tracked repository configuration — Priority: P1

**As a** LivingADR operator, **I want** the workflow service and MCP server to load tracked repositories from `living-adr.config.yaml`, **so that** repository onboarding is configuration-only and not hardcoded.

#### Acceptance Scenarios

- **Given** `living-adr.config.yaml` exists at the default path, **When** a deployable starts, **Then** it loads all configured repositories into a typed `LivingADRConfig` object.
- **Given** `LIVING_ADR_CONFIG` points to an alternate path, **When** a deployable starts, **Then** it reads that file instead of the default path.
- **Given** the file contains one repository entry, **When** the loader validates it, **Then** it uses the same list-based path as multiple repositories and does not branch on `single_repo`.

### [US-2] Validate repository identity and config — Priority: P1

**As a** downstream feature author, **I want** stable `RepositoryIdentity` and `RepositoryConfig` models, **so that** SCM calls, graph writes, MCP reads, and publish-back all share one scope contract.

#### Acceptance Scenarios

- **Given** duplicate repository identities are present, **When** config validation runs, **Then** startup fails with a clear duplicate-identity error.
- **Given** a repository identity is missing `host`, `owner`, `repo`, or `repo_id`, **When** config validation runs, **Then** startup fails with field-level validation detail.
- **Given** a valid repository entry, **When** code asks for its canonical key, **Then** the key is stable and formatted as `host/owner/repo` with `repo_id` retained separately.

### [US-3] Enforce publication and external-LLM policy from config — Priority: P1

**As a** security-conscious operator, **I want** ADR publication mode and external LLM egress to be explicit per repository, **so that** later GitHub publish-back and Claude calls cannot infer unsafe defaults.

#### Acceptance Scenarios

- **Given** `adr_publication_policy` is one of `livingadr_only`, `publish_to_github`, or `publish_to_github_and_livingadr`, **When** validation runs, **Then** the enum value is accepted and exposed to downstream services.
- **Given** publish-back is enabled, **When** target path or branch values are invalid or missing, **Then** startup fails before any webhook, graph, or MCP process becomes ready.
- **Given** `external_llm_allowed` is false, **When** later Claude-capable code queries repository policy, **Then** the config contract provides an explicit deny decision.

### [US-4] Make lifecycle semantics restart-required — Priority: P1

**As a** LivingADR operator, **I want** configuration changes to require process restart in the PoC, **so that** startup validation remains deterministic and hot-reload complexity is deferred.

#### Acceptance Scenarios

- **Given** the config file changes after startup, **When** a service continues running, **Then** the feature does not hot-reload or mutate the in-memory repository set.
- **Given** operators need changed config to take effect, **When** they restart workflow service and MCP server, **Then** both reload and validate the new file at startup.
- **Given** startup validation fails, **When** readiness or CLI startup result is inspected, **Then** the service reports configuration errors and does not silently continue with partial config.

### [US-5] Establish no-op Observability core port — Priority: P1

**As a** later feature implementer, **I want** a stable `Observability` port with a no-op implementation, **so that** features 003/008/009/010/012 can instrument without depending directly on LangSmith and feature 013 can swap in the real implementation.

#### Acceptance Scenarios

- **Given** a service has no LangSmith configuration, **When** it emits an observability event through the core port, **Then** the no-op implementation accepts the call without network I/O or failure.
- **Given** later code needs spans, counters, and structured events, **When** it imports the port, **Then** the method names and metadata-only contract are available from `core` without LangSmith dependencies.
- **Given** raw prompts, diffs, drafts, or reviewer comments are passed accidentally as metadata, **When** tests inspect the contract guidance, **Then** default-deny raw export expectations are documented for real implementations.

## Functional Requirements

- [FR-1] Define typed `RepositoryIdentity` and `RepositoryConfig` models aligned to `..\..\architecture.md#data-model`.
- [FR-2] Load `living-adr.config.yaml` from a well-known default path, with `LIVING_ADR_CONFIG` override.
- [FR-3] Support a list of repository entries and validate `N >= 1`; no implementation path may special-case exactly one repository.
- [FR-4] Reject duplicate canonical repository identities with actionable startup errors.
- [FR-5] Validate required identity fields, GitHub App installation id, default branch, ADR target branch, ADR path template, publication policy, and external LLM allow/deny flag.
- [FR-6] Parse `adr_publication_policy` as one of `livingadr_only`, `publish_to_github`, or `publish_to_github_and_livingadr`.
- [FR-7] Require publish target branch/path semantics when GitHub publication is enabled.
- [FR-8] Expose per-repository `external_llm_allowed: bool` for the future Claude adapter to enforce.
- [FR-9] Surface all config validation failures during application startup and prevent partial readiness.
- [FR-10] Document and test restart-required semantics; hot reload is not implemented.
- [FR-11] Define a thin `Observability` core port and `NoOpObservability` implementation with metadata-only event/span/counter methods.
- [FR-12] Keep secrets out of `RepositoryConfig`; secrets remain environment/vault concerns.

## Non-Functional Requirements

- [NFR-1] Deterministic validation: identical config content produces identical validated models and error messages suitable for startup diagnostics.
- [NFR-2] Security: repository config carries no secrets and external LLM egress is explicit deny/allow per repository.
- [NFR-3] Maintainability: all downstream services depend on typed core models/ports rather than parsing YAML directly.
- [NFR-4] Testability: config loading, validation, startup error formatting, policy parsing, restart semantics, and no-op observability are unit-testable without GitHub, Claude, LangSmith, graph storage, or network access.
- [NFR-5] Extensibility: PoC supports one configured repository but model shape remains compatible with multi-repo rollout.

## Scope

### In Scope

- `living-adr.config.yaml` schema, loader, and validation plan.
- `RepositoryIdentity`, `RepositoryConfig`, `PublicationPolicy`, and top-level config models.
- Startup diagnostics for invalid config in both `workflow-service` and `mcp-context-server` entry points.
- Publication-policy and external-LLM allow/deny parsing.
- Restart-required lifecycle semantics and tests proving no hot reload path exists.
- Thin no-op `Observability` core port/interface and unit tests.

### Out of Scope

- Hot reload or live repository-set mutation.
- GitHub App installation verification against the live GitHub API beyond syntactic config checks; feature 014 can expand onboarding diagnostics.
- Actual webhook ingestion, SCM API calls, graph storage, MCP tool implementation, Claude calls, LangSmith integration, or ADR publish-back.
- Multi-repo federation behavior beyond validating and iterating a list of repository entries.
- Secrets management implementation beyond excluding secrets from repository config.

## Themes, Metrics, and Failure Modes Served

- **Theme:** TH-07 Governance & Repository Onboarding.
- **MVP support:** Enables TH-01, TH-03, TH-04, TH-05, and TH-06 features to consume one repository-scope contract.
- **Success metrics:** Supports SM-02 by avoiding runtime ambiguity before PR-to-draft timing begins; supports SM-05 by ensuring repository scope/policy is explicit before authoritative mutations; indirectly supports SM-01/SM-03/SM-04 by enabling governed downstream flows.
- **Failure modes addressed:** FM-14 prompt/tool injection via explicit external LLM policy, FM-15/FM-16 MCP trust/auth mismatch via read-scoped config, FM-17 SCM replay complexity via stable repository identity, FM-21 sensitive trace leakage via default-deny observability contract, FM-23 docs-as-code without review gates via explicit publish policy, FM-24 cross-SCM abstraction leaks via provider-aware config.

## Dependencies

- **Project artifacts:** `..\..\architecture.md`, `..\..\domain-research.md`, `..\..\vision.md`, `..\..\feature-map.md`, `..\..\roadmap.md`.
- **Feature dependencies:** none (`depends_on: []` in `feature-map.md`).
- **Downstream consumers:** 003, 006, 012, 013, 014 and later 008/009/010/011.
- **Tech stack assumptions:** Python 3.12, Pydantic / `pydantic-settings`, PyYAML or equivalent YAML parser, pytest, FastAPI app startup hooks, uv package management.

## Success Criteria

- [ ] A valid one-repository `living-adr.config.yaml` validates through the same list-based path as multiple repositories.
- [ ] Invalid config stops startup with clear, actionable errors.
- [ ] Publication policy and external LLM allow/deny flags are parsed and available from typed config.
- [ ] No hot-reload behavior is implemented; restart-required semantics are documented and tested.
- [ ] `Observability` and `NoOpObservability` are defined in core and unit-tested without LangSmith.
- [ ] No repository config model includes secrets.

## Open Questions

- Exact default file location inside the eventual `C:\repos\living-adr` runtime should be finalized during scaffold/implementation; plan assumes repository root `living-adr.config.yaml` with `LIVING_ADR_CONFIG` override.
- Whether YAML parsing uses `pydantic-settings` custom sources, direct PyYAML loading into Pydantic models, or `pydantic-yaml` should be decided during implementation based on dependency policy.
