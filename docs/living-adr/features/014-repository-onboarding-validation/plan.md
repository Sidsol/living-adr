# Tactical Implementation Plan: repository-onboarding-validation

## Planning Assumptions

- Target repository for production code is `C:\repos\living-adr` as defined by `..\..\architecture.md#repositories`.
- Feature 002 has introduced config models/loader/startup diagnostics.
- Feature 003 has introduced GitHub provider/client seams for GitHub App credentials and repository-scoped API access.
- If no CLI framework exists, implement the same service behind a startup-check flag; do not block behavior on command spelling.
- This plan is for implementation preparation only; no production code is created by this artifact.

## Slice 1: Secret-safe onboarding diagnostics

### Files to Add/Change

| File | Action | Purpose |
|---|---|---|
| `src\living_adr\onboarding\__init__.py` | Add | Package boundary for onboarding code. |
| `src\living_adr\onboarding\diagnostics.py` | Add | `DiagnosticSeverity`, `DiagnosticCategory`, `OnboardingDiagnostic`, `OnboardingValidationResult`, formatter/redactor, exit-code helper. |
| `tests\onboarding\test_diagnostics.py` | Add | RED/GREEN tests for grouping, severity, remediation, safe metadata, redaction, and exit-code mapping. |

### Implementation Notes

- Categories: `config`, `environment`, `github_app`, `permissions`, `webhook_or_replay`, `lifecycle`.
- Severities: `info`, `warning`, `blocking`.
- Safe metadata allowlist should include repository key, config path, publication policy, installation id, default branch, permission names, and next step.
- Redaction should handle keys/names containing `secret`, `private_key`, `api_key`, `token`, `webhook`, `anthropic`, `langsmith`, and known raw content fields like `payload`, `diff`, `prompt`, `draft`, `reviewer_comment`.

### Verification

- Run focused diagnostic tests.
- Confirm formatted failure output is deterministic and grouped.

## Slice 2: Config, environment, and `.env.example` alignment

### Files to Add/Change

| File | Action | Purpose |
|---|---|---|
| `src\living_adr\onboarding\validation.py` | Add | `OnboardingValidator` service that loads config via feature 002, checks env names, emits lifecycle diagnostics, and later calls GitHub verification. |
| `src\living_adr\onboarding\required_env.py` or equivalent | Add | Central registry of required env variable names and descriptions for validation and `.env.example` drift tests. |
| `.env.example` | Add/Update | Placeholder-only setup file aligned with architecture and validation. |
| `tests\onboarding\test_validation_config_env.py` | Add | Config/env validation behavior with fake loader/env. |
| `tests\test_env_example.py` | Add | Static drift test ensuring every required env name appears exactly as a placeholder/comment in `.env.example`. |

### Required Environment Placeholder Set

- `LIVING_ADR_CONFIG`
- `GITHUB_APP_ID`
- `GITHUB_APP_PRIVATE_KEY_PATH`
- `GITHUB_WEBHOOK_SECRET`
- `ANTHROPIC_API_KEY`
- `LANGSMITH_API_KEY`
- `LIVING_ADR_UI_TOKEN`
- `LIVING_ADR_STORAGE_PATH` or the storage-path name finalized by the scaffold

If feature 002/003 use different exact names, prefer their names and update the registry/tests accordingly.

### Implementation Notes

- Never print env var values; only report missing/present status.
- Use feature 002's loader and `ConfigStartupError`; do not parse YAML here.
- Validate all configured repositories uniformly, but diagnostics may include an informational PoC note that operational support is one configured repository.
- Add lifecycle info: config is startup-read; restart `living-adr-workflow` and `living-adr-mcp` after changes.

### Verification

- Focused config/env tests pass.
- `.env.example` drift test passes.
- Search confirms no `.env.example` line contains plausible real secret material.

## Slice 3: GitHub App installation and permission verification

### Files to Add/Change

| File | Action | Purpose |
|---|---|---|
| `src\living_adr\scm\github_provider.py` | Change | Add or expose fakeable installation verification method if missing. |
| `src\living_adr\onboarding\github_checks.py` | Add optional helper | Keep onboarding-specific permission mapping thin; GitHub API details stay in provider. |
| `src\living_adr\onboarding\validation.py` | Change | Call GitHub verification for each repository config and convert responses/errors to diagnostics. |
| `tests\onboarding\test_github_installation_validation.py` | Add | Fake provider tests for installed/missing/suspended/wrong-repo/permission scenarios. |
| `tests\scm\test_github_provider_installation.py` | Add/Update | Provider/client seam tests if method added to SCM adapter. |

### Implementation Notes

- Proposed provider result shape: `InstallationVerification(repository_key, installation_id, repo_id, default_branch, permissions, status)`.
- Required permission mapping:
  - all policies: `contents:read`
  - `publish_to_github` and `publish_to_github_and_livingadr`: `contents:write`
- Treat installation not found, repository not accessible, suspended installation, bad credentials, and rate limit as distinct diagnostic error types where feature 003's error taxonomy supports it.
- Keep raw GitHub payloads out of diagnostics.

### Verification

- Fake-client tests cover all status branches.
- No test makes live network calls by default.
- Search confirms onboarding command/service does not import `httpx` directly unless that is already the provider abstraction convention.

## Slice 4: Operator command/startup check integration

### Files to Add/Change

| File | Action | Purpose |
|---|---|---|
| `src\living_adr\cli.py` or app CLI module | Add/Change | Wire `onboard validate` (preferred) or `--check-onboarding` to `OnboardingValidator`. |
| `src\living_adr\apps\workflow_service\startup.py` | Optional change | If startup-check flag is selected, expose validation before service readiness. |
| `tests\onboarding\test_cli_onboarding.py` | Add | Command runner tests for exit 0/non-zero and output safety. |
| `README.md` or existing operator docs | Update only if present | Brief command usage and restart-required note; do not add broad runbook if no docs convention exists. |

### Implementation Notes

- CLI wrapper should not parse YAML or call GitHub directly.
- Output on success: repository key, config path, publication policy, installation id, required permissions satisfied, restart-required note, next step (`start workflow service` or `send replay fixture/webhook`).
- Output on failure: grouped diagnostics, remediation, no secrets.
- Exit status: 0 pass, non-zero when any blocking diagnostic exists.

### Verification

- CLI tests pass for success/failure.
- Full existing test suite and lint command pass after implementation.

## Cross-Cutting Verification Plan

Use existing project commands only, likely:

- `uv run pytest`
- `uv run ruff check`

Additional manual/self-review checks:

- Confirm no files implement hot reload, file watchers, background reload tasks, automatic GitHub installation, or repo discovery.
- Confirm diagnostics and `.env.example` contain placeholders only and no real secrets.
- Confirm direct GitHub API details stay within `scm` adapter/provider files.
- Confirm all new code paths accept/use `RepositoryIdentity` scope.

## File-Level Dependency Order

1. `tests\onboarding\test_diagnostics.py` → `src\living_adr\onboarding\diagnostics.py`
2. `tests\onboarding\test_validation_config_env.py` + `tests\test_env_example.py` → `required_env.py`, `.env.example`, `validation.py`
3. `tests\onboarding\test_github_installation_validation.py` → provider verification method/helper and validation integration
4. `tests\onboarding\test_cli_onboarding.py` → CLI/startup wrapper
5. Full test/lint verification
