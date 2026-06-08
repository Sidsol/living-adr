# Feature Specification: repository-onboarding-validation

## Overview

Feature 014 hardens the PoC path for adding or verifying the single tracked GitHub repository used by LivingADR. It adds operator-facing onboarding validation around the contracts from feature 002 (`RepositoryIdentity`, `RepositoryConfig`, `living-adr.config.yaml`, startup diagnostics) and feature 003 (`GitHubProvider`, GitHub App installation credentials, webhook/evidence access). The feature verifies GitHub App installation status, aligns `.env.example` with required non-secret environment variables, improves config validation diagnostics, and exposes a CLI or documented startup check that operators can run before expecting webhook ingestion to work.

This is P2 TH-07 hardening after the MVP path exists. It intentionally does not implement hot reload, broad multi-repo governance automation, repository ownership policy, or enterprise rollout workflows.

## User Stories

### [US-1] Run a repository onboarding validation check — Priority: P1

**As a** LivingADR operator, **I want** a deterministic CLI or startup-check command that validates the configured PoC repository, **so that** I can diagnose setup problems before processing GitHub webhook deliveries.

#### Acceptance Scenarios

- **Given** `living-adr.config.yaml` points to one valid configured repository, **When** the operator runs the onboarding check, **Then** the command reports the repository identity, config file path, and overall pass/fail status without exposing secrets.
- **Given** the config file is missing or invalid, **When** the onboarding check runs, **Then** it reuses feature 002 validation and prints actionable field-path diagnostics.
- **Given** multiple repositories are configured in a future-compatible config file, **When** the onboarding check runs during PoC, **Then** it validates each entry uniformly but labels the PoC expectation that exactly one repository is supported operationally.

### [US-2] Verify GitHub App installation for the configured repository — Priority: P1

**As a** LivingADR operator, **I want** onboarding to verify the configured GitHub App installation id can access the tracked repository with required permissions, **so that** webhook ingestion and publish policy prerequisites are known before runtime.

#### Acceptance Scenarios

- **Given** valid GitHub App credentials and an installed app for the configured repository, **When** onboarding verification runs, **Then** it confirms installation id, repository access, and minimum permissions required by the repository's publication policy.
- **Given** the installation id is absent, wrong, suspended, or not installed on the configured repository, **When** verification runs, **Then** it fails with a remediation message naming the repository key and installation id but not private key material.
- **Given** `adr_publication_policy` is `livingadr_only`, **When** permissions are checked, **Then** `contents:read` is sufficient.
- **Given** `adr_publication_policy` includes GitHub publication, **When** permissions are checked, **Then** missing `contents:write` is reported as a blocking diagnostic.

### [US-3] Align examples and diagnostics with required environment/config inputs — Priority: P1

**As a** first-time PoC operator, **I want** `.env.example`, sample config, and validation output to describe the same required inputs, **so that** setup instructions do not drift from runtime expectations.

#### Acceptance Scenarios

- **Given** `.env.example` is generated or updated, **When** an operator compares it with startup/onboarding requirements, **Then** all required non-secret keys are present with placeholders and comments.
- **Given** secrets are required, **When** `.env.example` is reviewed, **Then** it contains placeholders only and no real secret values.
- **Given** onboarding fails due to missing environment variables, **When** diagnostics are printed, **Then** they reference the same variable names as `.env.example`.

### [US-4] Surface operator diagnostics without broad governance automation — Priority: P2

**As a** LivingADR operator, **I want** concise diagnostics and readiness output for config, GitHub App installation, webhook readiness, and restart requirements, **so that** I know what to fix without relying on multi-repo automation.

#### Acceptance Scenarios

- **Given** onboarding checks fail, **When** the command exits, **Then** it returns a non-zero exit code and grouped diagnostics by category: config, environment, GitHub App, permissions, webhook/replay path, and restart lifecycle.
- **Given** onboarding checks pass, **When** the command exits, **Then** it reports safe metadata only: repository key, default branch, publication policy, installation id, and next operational step.
- **Given** config changes after startup, **When** diagnostics are displayed, **Then** they state that both `living-adr-workflow` and `living-adr-mcp` must be restarted; no watcher or hot reload is implied.

## Functional Requirements

- [FR-1] Provide a repository onboarding validation entrypoint, implemented as a CLI command or documented startup check, that can be run independently of webhook delivery processing.
- [FR-2] Reuse feature 002's `load_living_adr_config`, `RepositoryIdentity`, `RepositoryConfig`, and config diagnostic types rather than parsing YAML independently.
- [FR-3] Reuse feature 003's `GitHubProvider` / GitHub App credential handling seam for installation checks; do not create a second GitHub API client path.
- [FR-4] Verify the configured GitHub App installation id is installed for each configured repository identity and can obtain/access repository metadata.
- [FR-5] Validate permission prerequisites: `contents:read` for all repositories; `contents:write` when `adr_publication_policy` publishes to GitHub.
- [FR-6] Detect mismatches among `RepositoryIdentity.host/owner/repo/repo_id`, GitHub API repository metadata, default branch, installation id, and publication policy target branch/path.
- [FR-7] Keep diagnostics operator-readable, grouped, deterministic, and safe for logs; never print private keys, webhook secrets, Anthropic keys, LangSmith keys, UI tokens, raw webhook payloads, or diffs.
- [FR-8] Align `.env.example` with all required environment variables for config path, GitHub App credentials, webhook secret placeholder, Anthropic key placeholder, LangSmith key placeholder, UI token placeholder, and storage paths.
- [FR-9] Add tests for passing onboarding, config failures, env failures, GitHub installation failures, permission failures, and `.env.example` drift.
- [FR-10] Preserve PoC lifecycle semantics: checks are startup/CLI-time only; no hot reload, long-running watcher, automatic repo discovery, or multi-repo rollout automation.

## Non-Functional Requirements

- [NFR-1] Security: diagnostics and example files must be secret-safe and must not export raw repository payloads or credentials.
- [NFR-2] Testability: GitHub installation verification must be testable with fake GitHub clients/responses; no live GitHub dependency in unit tests.
- [NFR-3] Maintainability: onboarding checks are thin orchestration over feature 002 and 003 seams, not duplicate validation or duplicate GitHub adapters.
- [NFR-4] Operational clarity: errors must include remediation hints and exit codes suitable for scripts or local startup troubleshooting.
- [NFR-5] Extensibility: implementation should iterate `RepositoryConfig` entries uniformly even though the PoC validates one tracked repository.

## Scope

### In Scope

- CLI or documented startup validation check for repository onboarding.
- Live GitHub App installation verification through the existing GitHub provider seam.
- Permission checks tied to publication policy.
- Config/environment diagnostic formatting and exit status.
- `.env.example` and sample config alignment checks.
- Operator-facing restart-required and webhook/replay prerequisite diagnostics.

### Out of Scope

- Hot reload or dynamic repository-set mutation.
- Automatic repository discovery, repository ownership mapping, or multi-repo governance automation.
- Creating or installing the GitHub App automatically.
- Azure DevOps onboarding.
- Webhook ingestion implementation itself, dead-letter replay implementation, ADR publish-back, Claude drafting, graph mutations, or MCP query behavior.
- Storing secrets in `living-adr.config.yaml` or generated docs.

## Themes, Metrics, and Failure Modes Served

- **Theme:** TH-07 Governance & Repository Onboarding.
- **MVP support:** Hardens the single-repo PoC setup after features 002 and 003 are available and supports M5 operational readiness in `..\..\roadmap.md`.
- **Success metrics:** Supports SM-02 by preventing misconfigured repositories from silently consuming PR-to-draft latency; supports SM-05 by verifying repository scope and publication permissions before authoritative flows; indirectly supports SM-01 by reducing setup-caused false negatives.
- **Failure modes addressed:** FM-17 webhook replay/setup complexity, FM-18 rate-limit/permission risk, FM-21 sensitive data in traces/logs, FM-23 docs-as-code without review gates, FM-24 cross-SCM abstraction leaks.

## Dependencies

- **Project artifacts:** `..\..\architecture.md`, `..\..\domain-research.md`, `..\..\vision.md`, `..\..\feature-map.md`, `..\..\roadmap.md`.
- **Feature dependencies:** feature 002 `tracked-repository-configuration`; feature 003 `github-webhook-ingestion`.
- **Architecture anchors:** `..\..\architecture.md#repositories`, `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#deployment`, `..\..\architecture.md#anti-patterns`.

## Success Criteria

- [ ] A local operator can run one onboarding validation command/check and receive pass/fail output for the configured PoC repository.
- [ ] GitHub App installation id, repository access, and publication-policy permissions are verified with fake-client unit coverage.
- [ ] Config and environment diagnostics reuse feature 002 semantics and match `.env.example` variable names.
- [ ] `.env.example` contains all required placeholders and no real secrets.
- [ ] Diagnostics state restart-required lifecycle and do not imply hot reload.
- [ ] No broad multi-repo governance automation, automatic discovery, or Azure DevOps onboarding is introduced.

## Open Questions

- Should the implementation expose the check as `living-adr onboard validate` or as a documented `living-adr-workflow --check-onboarding` startup mode? The plan supports either, with CLI preferred for operator ergonomics.
- What exact GitHub App non-contents permissions are required after feature 003 finalizes its webhook event list? This feature should consume the finalized permission contract rather than inventing one.
