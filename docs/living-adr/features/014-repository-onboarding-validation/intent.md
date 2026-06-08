# Architecture Intent: repository-onboarding-validation

## Current State

LivingADR is greenfield, but the project architecture already defines repository onboarding constraints. The single implementation repository is `living-adr` (`..\..\architecture.md#repositories`), with shared `core` contracts and two deployables. The high-level data model names `RepositoryIdentity` and `RepositoryConfig`, including GitHub App installation id and publication policy (`..\..\architecture.md#data-model`). Cross-cutting concerns require `living-adr.config.yaml`, env/vault secrets, `.env.example`, GitHub App least-privilege permissions, startup validation, no hot reload, and clear validation if installation ids are not installed (`..\..\architecture.md#cross-cutting`). Local deployment depends on configured GitHub App credentials and a webhook delivery path or replay fixture (`..\..\architecture.md#deployment`). Anti-patterns warn against SCM replay gaps, broad mining/rate-limit waste, sensitive trace leakage, docs-as-code without review gates, and cross-SCM leaks (`..\..\architecture.md#anti-patterns`).

Feature 002 supplies the typed configuration seam and startup diagnostics but explicitly leaves live GitHub App installation verification to this feature. Feature 003 supplies the GitHub App webhook/SCM provider seam and normalized ingestion contracts. No feature yet gives operators a single preflight path to know whether the configured PoC repository is actually ready.

## Desired State

After this feature, a LivingADR operator can run one onboarding validation command or documented startup-check mode for the configured PoC repository. The check loads `living-adr.config.yaml` through feature 002, verifies required environment placeholders/values without leaking secrets, verifies the configured GitHub App installation through feature 003's GitHub provider seam, checks permissions implied by `adr_publication_policy`, reports grouped diagnostics, and exits non-zero on blocking failures.

The implementation remains PoC-scoped: it validates the configured repository list uniformly but does not discover repositories, manage installations, implement hot reload, or automate multi-repo governance rollout.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Config loading | Feature 002 loader/model/startup diagnostics | Onboarding preflight reuses same validation and messages | Add orchestration command/check |
| GitHub installation | Feature 002 excludes live checks; feature 003 handles GitHub App API for ingestion | Installation id, repo access, and permissions verified before runtime | Add fakeable verification method/service |
| `.env.example` | Architecture requires placeholders | Example aligned with required env names and diagnostics | Add/update example plus drift test |
| Operator diagnostics | Config and ingestion errors are separate | Grouped config/env/GitHub/permission/webhook/lifecycle output | Add diagnostic model and formatter |
| Lifecycle | No hot reload from feature 002 and architecture | Onboarding output reiterates restart requirement | Include lifecycle diagnostic, no watchers |
| Scope control | TH-07 includes future governance | Feature only hardens single-repo PoC | Explicitly reject discovery/governance automation |

## Architecture Options

### Option A: Manual runbook only

**Approach:** Document manual config and GitHub App checks without adding executable validation.

- ✅ Pros: Minimal implementation.
- ❌ Cons: Cannot enforce drift, weak diagnostics, not scriptable, easy for setup to remain broken until first webhook.
- 🔧 Effort: Low.

### Option B: CLI onboarding validation over existing seams (selected)

**Approach:** Implement a CLI-style validation path (`living-adr onboard validate` or equivalent startup check) backed by an onboarding validation service. It consumes feature 002 config contracts and feature 003 GitHub provider handles.

- ✅ Pros: Operator-friendly, testable, keeps validation close to runtime contracts, supports M5 hardening, avoids duplicate YAML/GitHub code.
- ❌ Cons: Adds a small CLI/diagnostic surface and requires careful fake-client tests.
- 🔧 Effort: Medium.

### Option C: Repository onboarding controller with discovery and reload

**Approach:** Continuously inspect GitHub installations, discover repos, update config, and reload services.

- ✅ Pros: Future multi-repo ergonomics.
- ❌ Cons: Violates PoC scope, introduces hot reload, governance automation, and broader permissions.
- 🔧 Effort: High.

## Selected Approach

Select Option B. The feature should add a small validation service and a thin command/startup-check wrapper. The service should:

1. Load config using feature 002's `load_living_adr_config` and surface `ConfigStartupError` unchanged where possible.
2. Validate required environment names and `.env.example` alignment without reading or printing secret values beyond presence/absence.
3. Use feature 003's `GitHubProvider` or adapter-owned client to verify installation id, repository metadata, default branch, and permissions.
4. Produce grouped diagnostics with severity, category, repository key, remediation, and safe metadata.
5. Return deterministic exit/readiness status.

## Bound Contracts

### Feature 002 Config Validation Contract

- Reuse `RepositoryIdentity` as the canonical repository key; do not create onboarding-specific identity strings.
- Reuse `RepositoryConfig` for `github_app_installation_id`, `default_branch`, `adr_publication_policy`, `adr_target_branch`, `adr_path_template`, and `external_llm_allowed`.
- Reuse `ConfigStartupError` or equivalent field-path diagnostics for invalid YAML/config.
- Keep `RepositoryConfig` secret-free; GitHub private key, webhook secret, Anthropic key, LangSmith key, and UI token remain environment/vault concerns.
- Respect restart-required lifecycle; no hot reload or watcher.

### Feature 003 GitHub App Handles Contract

- Reuse `GitHubProvider` / `SCMProvider` credential flow for installation-token access.
- Verification should accept `RepositoryIdentity`/`RepositoryConfig` and return installation/repository metadata without leaking raw GitHub payloads to callers.
- Provider-specific API shape remains in `scm`; onboarding diagnostics should expose provider-neutral categories plus GitHub-specific remediation text only where useful.
- Tests use fake provider/client responses; live GitHub integration is optional/manual.

## Module Surface Analysis

| Module | Inputs | Callers | Deletion test | Isolated-test candidate |
|---|---:|---|---|---|
| `src\living_adr\onboarding\diagnostics.py` | validation events, safe metadata | CLI, startup check, tests | Deleting removes grouped operator output and redaction boundary | Yes — pure formatting/redaction tests |
| `src\living_adr\onboarding\validation.py` | config path/env, `LivingADRConfig`, GitHub provider, observability | CLI/startup check | Deleting removes onboarding preflight behavior | Yes — fake loader/provider/env |
| `src\living_adr\cli.py` or `apps\workflow_service\cli.py` | command args, process env | operator | Deleting removes command path but not service | Partially — command runner tests |
| `src\living_adr\scm\github_provider.py` | GitHub App credentials, `RepositoryIdentity`, installation id | onboarding validation, ingestion | Deleting installation verification breaks live onboarding readiness | Yes with fake HTTP/client |
| `.env.example` | placeholder env var names | operators, drift tests | Deleting loses setup alignment | Yes — static content test |
| `tests\onboarding\test_validation.py` | fake configs/providers/env | pytest | Deleting loses onboarding behavior coverage | n/a |
| `tests\onboarding\test_diagnostics.py` | diagnostic fixtures/secrets | pytest | Deleting risks secret leakage and bad exit output | n/a |
| `tests\test_env_example.py` | required env registry/example file | pytest | Deleting permits setup docs drift | n/a |

## Anti-Patterns to Avoid

- **Re-parsing YAML in onboarding:** duplicates feature 002 and causes drift.
- **Direct GitHub API calls from CLI:** bypasses feature 003 provider seam and leaks GitHub assumptions.
- **Printing secrets or raw payloads:** violates `..\..\architecture.md#cross-cutting` default-deny diagnostics.
- **Auto-discovering repositories:** turns P2 PoC hardening into multi-repo governance automation.
- **Hot reload watcher:** violates PoC lifecycle and deployment assumptions.
- **Treating installation verification as webhook ingestion:** this feature verifies prerequisites only; feature 003 owns ingestion behavior.
- **Assuming write permissions always required:** `contents:write` is only required when publication policy publishes to GitHub.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add onboarding validation service/CLI, safe diagnostics, GitHub App installation verification through SCM adapter, `.env.example` alignment tests | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GitHub permission model changes or feature 003 finalizes a different permission list | Medium | Medium | Centralize required permissions in adapter/config helper and keep tests policy-driven. |
| Operators mistake pass status as broad rollout readiness | Low | Medium | Output labels PoC single-repo validation and explicitly excludes governance automation. |
| Drift between `.env.example` and runtime env names | Medium | Medium | Add static drift test over required environment registry. |
| Secret redaction misses a value | Medium | High | Formatter tests include private key, webhook secret, API key, token, and URL-ish values. |
| CLI framework not present yet | Medium | Low | Keep service independent; expose as startup `--check-onboarding` if CLI scaffold is unavailable. |

## Readiness Decision

Ready for implementation planning. The only open choice is command spelling versus startup-check flag; it does not alter slice boundaries or contracts. The implementation manifest should set `ready: true` with this assumption documented.
