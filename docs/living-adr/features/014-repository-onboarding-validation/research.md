# Feature Research: repository-onboarding-validation

## Research Scope

This research focuses on feature 014 only: PoC repository onboarding validation for the single tracked GitHub repository. It binds to project-level artifacts and to feature dependencies 002 and 003. It does not design production code beyond planning seams.

## Source Review

| Source | Relevant Findings |
|---|---|
| `..\..\vision.md` | LivingADR MVP is a 1 repository / 1 user PoC. TH-07 covers governance and repository onboarding. Multi-repo rollout and governance automation are explicitly post-PoC. |
| `..\..\domain-research.md` | GitHub Apps provide fine-grained repository installation scope; webhooks require signature validation, idempotency, retry/replay, and rate-limit awareness. Common failures include SCM event duplication/replay complexity (FM-17), rate-limit starvation (FM-18), sensitive trace leakage (FM-21), docs-as-code without review gates (FM-23), and cross-SCM abstraction leaks (FM-24). |
| `..\..\architecture.md#repositories` | Production code lives in one `living-adr` repo with two deployables: `workflow-service` and `mcp-context-server`. Local PoC runs from `C:\repos\living-adr`. |
| `..\..\architecture.md#data-model` | `RepositoryIdentity` and `RepositoryConfig` are foundational contracts. `RepositoryConfig` includes GitHub App installation id, default branch, ADR publication policy, target branch/path, and external LLM policy. |
| `..\..\architecture.md#cross-cutting` | Configuration/secrets must be split: config in `living-adr.config.yaml`; secrets in env/vault or `.env.local`; scaffold creates `.env.example`, not real secrets. GitHub App permissions differ by publication policy. Config is startup-read only; no hot reload in PoC. |
| `..\..\architecture.md#deployment` | Local PoC requires GitHub App credentials and either webhook delivery path or replay fixture. Both deployables run locally and share persistence conventions. |
| `..\..\architecture.md#anti-patterns` | Onboarding must avoid replay gaps, broad history mining, sensitive data leakage, GitHub-specific leakage outside SCM adapters, and docs-as-code without review gates. |
| `..\..\feature-map.md` | Feature 014 is P2 TH-07, ~4 slices, depends on 002 and 003, and covers CLI/startup checks, GitHub App installation verification, config validation messages, `.env.example` alignment, and operator diagnostics without multi-repo governance automation or hot reload. |
| `..\..\roadmap.md` | Feature 014 lands in M5 Operational and Onboarding Hardening. Exit criterion includes GitHub App installation, config, `.env.example`, and diagnostics validation for the single PoC repo. |
| `..\002-tracked-repository-configuration\intent.md` | Feature 002 selects Pydantic core config models with shared loader, clear startup errors, no secrets in repository config, restart-required semantics, and no live GitHub validation. Feature 014 owns live installation diagnostics. |
| `..\003-github-webhook-ingestion\intent.md` | Feature 003 selects provider-neutral `SCMEvent`/`SCMProvider` with `GitHubProvider` adapter, raw HMAC verification, config-scoped repository resolution, idempotency, replay/dead-letter, and metadata-only observability. Feature 014 should reuse the GitHub provider seam for installation verification. |

## Existing Contract Surfaces to Reuse

### From Feature 002

- `RepositoryIdentity`: provider-neutral scope key (`host/owner/repo` plus `repo_id`).
- `RepositoryConfig`: repository onboarding and policy record with no secrets.
- `LivingADRConfig`: top-level repository collection and lookup helpers.
- `load_living_adr_config(...)`: config path resolution and validation.
- `ConfigStartupError`: operator-readable startup validation failures.
- Restart-required semantics: load once at startup, no watcher or runtime mutation.

Feature 014 must not reimplement YAML parsing or duplicate field validation. It should layer live checks and diagnostics on top of these contracts.

### From Feature 003

- `SCMProvider` and `GitHubProvider`: GitHub App and repository API seam.
- GitHub installation credential flow using app id/private key and short-lived installation tokens.
- Repository-scoped method signatures accepting `RepositoryIdentity`.
- Provider-specific details isolated in `scm\github_provider.py` / related adapter modules.
- Metadata-only observability and error classification expectations.

Feature 014 should avoid direct ad-hoc `httpx` GitHub calls except through adapter-owned client abstractions.

## Gap Analysis

| Area | Current After Dependencies | Needed for Feature 014 | Gap |
|---|---|---|---|
| Config syntax validation | Feature 002 validates YAML/model shape | Onboarding command/check reuses and presents diagnostics | Add orchestration and grouped output |
| Live GitHub installation check | Feature 002 intentionally excludes it; feature 003 has GitHub provider seam | Verify installation id can access configured repo and permissions | Add provider method or onboarding service using fakeable GitHub client |
| Permission-policy mapping | Architecture states `contents:read` vs `contents:write` by publish policy | Operator sees blocking diagnostic when App lacks required permission | Add policy-to-permission check and tests |
| Environment examples | Architecture requires `.env.example` placeholders | Example aligns with required env names and diagnostics | Add/update example and drift test |
| Operator diagnostics | Startup errors exist; webhook handling errors exist | Unified onboarding categories and exit status | Add diagnostic model/formatter |
| Lifecycle messaging | Feature 002 documents no hot reload | Onboarding output reminds restart required | Add lifecycle diagnostic, no watcher |

## Architecture Options

### Option A: Document-only startup checklist

**Approach:** Add README/runbook instructions telling operators how to validate config and GitHub App installation manually.

- ✅ Pros: Lowest implementation cost; no new CLI surface.
- ❌ Cons: Easy to drift from runtime behavior; cannot be tested thoroughly; weaker PoC ergonomics.
- 🔧 Effort: Low.

### Option B: CLI onboarding validation command over existing config and SCM seams (selected)

**Approach:** Add a command such as `living-adr onboard validate` that loads config via feature 002, verifies environment placeholders/required values, calls feature 003's GitHub provider seam to verify installation/repository/permissions, and returns grouped diagnostics with non-zero exit on failure.

- ✅ Pros: Testable, scriptable, operator-friendly, reuses existing seams, prevents docs/runtime drift, clear fit for M5 hardening.
- ❌ Cons: Adds a small CLI surface and requires careful fake-client testing.
- 🔧 Effort: Medium.

### Option C: Background self-healing onboarding service

**Approach:** Run a service that continuously discovers repositories, manages GitHub App installation status, and reloads config dynamically.

- ✅ Pros: Better for broad rollout.
- ❌ Cons: Violates PoC constraints; introduces hot reload, automation governance, and repository discovery outside scope.
- 🔧 Effort: High.

## Selected Approach

Select Option B. A CLI-style validation check gives operators one deterministic path to validate the PoC repository while preserving the architecture's source-of-truth and secret boundaries. If the eventual app scaffold lacks a CLI framework, the same behavior can be implemented as a documented startup `--check-onboarding` mode, but it should still be backed by the same service and tests.

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Onboarding duplicates feature 002 validation | Medium | Medium | Use `load_living_adr_config` and diagnostic types directly; tests should mock loader only at service boundary. |
| GitHub checks bypass feature 003 adapter | Medium | High | Add fakeable methods to `GitHubProvider`/SCM seam or use its client abstraction; no direct API calls from CLI. |
| Diagnostics leak secrets | Medium | High | Formatter redacts secret-like fields; `.env.example` placeholders only; tests assert secret strings are absent. |
| Permission checks overfit GitHub | Medium | Medium | Keep permission verification in GitHub adapter/onboarding GitHub component; expose provider-neutral diagnostic categories. |
| Live GitHub tests become flaky | High | Medium | Unit tests use fake GitHub responses; optional manual integration check is separate and skipped by default. |
| CLI implies multi-repo governance | Low | Medium | Validate lists uniformly but label PoC operational support as one repo; no discovery/rollout automation. |
| Hot reload sneaks in for ergonomics | Low | Medium | State restart-required in diagnostics and checklist; prohibit file watchers/reload loops. |

## Recommended Module Surface

| Module | Purpose | Notes |
|---|---|---|
| `src\living_adr\onboarding\validation.py` | Pure orchestration service for config/env/GitHub checks and diagnostic aggregation | Depends on feature 002 models and feature 003 provider interfaces. |
| `src\living_adr\onboarding\diagnostics.py` | Diagnostic severity/category/result model and secret-safe formatter | Unit-testable without network. |
| `src\living_adr\cli.py` or app CLI module | Command entrypoint for `onboard validate` or equivalent | Thin wrapper around validation service. |
| `src\living_adr\scm\github_provider.py` | Add fakeable installation/permission verification method if feature 003 does not already expose one | Keeps GitHub API shape inside SCM adapter. |
| `.env.example` | Non-secret placeholder alignment with runtime requirements | No real credentials. |
| `tests\onboarding\test_validation.py` | Happy/failure path tests with fakes | Covers config, env, GitHub, permissions. |
| `tests\onboarding\test_diagnostics.py` | Formatter/redaction/exit behavior tests | Guards log safety. |
| `tests\test_env_example.py` | Drift test between required env names and example placeholders | Prevents onboarding docs drift. |

## Research Conclusion

Feature 014 is ready to plan as four slices: diagnostic model, config/env/example alignment, GitHub App installation verification, and CLI/startup integration. Readiness should be `true` because dependencies are planned, scope is bounded, and the key open CLI-name question can be resolved during implementation without changing behavior.
