# CRISPY Checklist: repository-onboarding-validation

## Scope Gates

- [ ] Feature remains limited to PoC repository onboarding validation for the configured single tracked repository.
- [ ] No production code creates broad multi-repo governance automation, ownership mapping, repo discovery, or rollout workflows.
- [ ] No hot reload, file watcher, background config polling, or runtime repository-set mutation is introduced.
- [ ] Azure DevOps onboarding remains out of scope.

## Dependency Gates

- [ ] Config loading and field validation reuse feature 002 contracts (`RepositoryIdentity`, `RepositoryConfig`, `LivingADRConfig`, loader, startup diagnostics).
- [ ] GitHub App installation verification reuses feature 003 GitHub provider/client handles; no duplicate direct GitHub API path is added in CLI/onboarding code.
- [ ] All checks preserve `RepositoryIdentity` scope and avoid onboarding-specific identity formats.

## GitHub App Install Verification

- [ ] Onboarding validates configured GitHub App installation id for the configured repository.
- [ ] Missing, wrong, suspended, or inaccessible installation states produce blocking diagnostics.
- [ ] Repository metadata mismatches (`repo_id`, owner/repo, default branch where available) are reported safely.
- [ ] Permission checks enforce `contents:read` for `livingadr_only`.
- [ ] Permission checks enforce `contents:write` for `publish_to_github` and `publish_to_github_and_livingadr`.
- [ ] GitHub verification tests use fake clients/providers; no live GitHub network call is required in unit tests.

## Config Validation Diagnostics

- [ ] Invalid config diagnostics are actionable and include field paths or repository keys where available.
- [ ] Diagnostics group errors by config, environment, GitHub App, permissions, webhook/replay prerequisite, and lifecycle.
- [ ] Blocking failures return non-zero exit/readiness status.
- [ ] Passing checks return safe setup metadata and a clear next operational step.

## `.env.example` Alignment

- [ ] `.env.example` includes placeholders for all required environment variables.
- [ ] `.env.example` contains no real secrets, private key material, API keys, webhook secrets, or tokens.
- [ ] Runtime diagnostic variable names match `.env.example` names.
- [ ] A test or static check prevents required-env drift from `.env.example`.

## Operator Diagnostics and Safety

- [ ] Diagnostics never print GitHub private keys, webhook secrets, Anthropic keys, LangSmith keys, UI tokens, raw webhook payloads, diffs, prompts, provisional ADR drafts, or reviewer comments.
- [ ] Success output may include only safe metadata: repository key, config path, default branch, publication policy, installation id, required permission names, and next step.
- [ ] Output states that config changes require restarting both `living-adr-workflow` and `living-adr-mcp`.
- [ ] Command/help text labels the feature as PoC onboarding validation, not automated governance rollout.

## Architecture Anchor Gates

- [ ] `..\..\architecture.md#repositories`: implementation targets the single `living-adr` repo and local PoC deployables.
- [ ] `..\..\architecture.md#data-model`: `RepositoryIdentity` and `RepositoryConfig` remain the source of truth.
- [ ] `..\..\architecture.md#cross-cutting`: config/secrets split, least privilege, startup validation, `.env.example`, and no-hot-reload requirements are followed.
- [ ] `..\..\architecture.md#deployment`: local operator flow works before webhook/replay processing.
- [ ] `..\..\architecture.md#anti-patterns`: FM-17, FM-18, FM-21, FM-23, and FM-24 are explicitly mitigated.

## Test and Verification Gates

- [ ] RED tests exist before GREEN implementation for diagnostics, config/env validation, GitHub installation verification, permission checks, and command wrapper.
- [ ] Focused onboarding tests pass.
- [ ] Full existing test suite passes.
- [ ] Existing lint command passes.
- [ ] Final self-review confirms no out-of-scope automation and no secrets in docs/examples/logging.

## Ready-to-Implement Gate

- [ ] `spec.md`, `research.md`, `intent.md`, `outline.md`, `plan.md`, `tasks.md`, `checklist.md`, and `implementation-manifest.yaml` are internally consistent.
- [ ] Slice count is 4.
- [ ] Implementation manifest sets `ready: true` unless a dependency contract is missing.
