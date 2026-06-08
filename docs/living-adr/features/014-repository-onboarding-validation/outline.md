# Implementation Outline: repository-onboarding-validation

## Slice Strategy

The feature is decomposed into four vertical slices matching the feature-map estimate. The order first creates safe diagnostic primitives, then binds config/environment/example alignment to feature 002, then adds GitHub App installation verification through feature 003, and finally exposes the operator command/startup check. This keeps network-facing behavior fakeable and prevents CLI code from owning validation logic.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| 1 | Secret-safe onboarding diagnostics | US-1, US-4 | S | — | false | AFK | Pure diagnostic model/formatter with deterministic redaction and exit semantics. |
| 2 | Config, environment, and `.env.example` alignment | US-1, US-3, US-4 | M | 1 | false | HITL | Reuses feature 002 config semantics and defines operator-facing setup contract. |
| 3 | GitHub App installation and permission verification | US-2, US-4 | M | 1, 2 | false | HITL | Touches live SCM trust/permission boundary and must reuse feature 003 provider handles. |
| 4 | Operator command/startup check integration | US-1, US-4 | S | 2, 3 | false | AFK | Thin wrapper over validated service plus end-to-end command behavior. |

## Slices

### Slice 1: Secret-safe onboarding diagnostics

**Scope:** Define diagnostic categories, severities, result aggregation, safe metadata, formatter, and exit/readiness semantics.

**User Stories:** US-1, US-4

**Automation:** AFK

**Automation Reason:** No external boundary; deterministic pure logic can be implemented and reviewed through tests.

**Deliverables:**

- `src\living_adr\onboarding\diagnostics.py` with categories: config, environment, github_app, permissions, webhook_or_replay, lifecycle.
- Secret-safe formatter that redacts private keys, webhook secrets, API keys, LangSmith keys, UI tokens, and token-like values.
- `tests\onboarding\test_diagnostics.py`.

**Checkpoint Criteria:**

- [ ] Blocking diagnostics produce failed result and non-zero exit code mapping.
- [ ] Passing result reports safe metadata only.
- [ ] Formatter groups diagnostics by category and includes remediation text.
- [ ] Tests prove secret-like values are redacted and raw payload/diff fields are not emitted.

**Context Notes:**

- Architecture anchors: `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#anti-patterns`.
- Estimated complexity: Low.

### Slice 2: Config, environment, and `.env.example` alignment

**Scope:** Build the validation service shell that loads feature 002 config, checks required environment variable presence by name, validates `.env.example` placeholders, and emits restart-required lifecycle diagnostics.

**User Stories:** US-1, US-3, US-4

**Automation:** HITL

**Automation Reason:** Operator setup contract must match architecture and feature 002 behavior; human review should confirm scope and names.

**Deliverables:**

- `src\living_adr\onboarding\validation.py` with config/env/example checks and injectable loader/env.
- Required environment registry shared with diagnostics/example tests.
- `.env.example` placeholders/comments for required non-secret keys.
- `tests\onboarding\test_validation_config_env.py` and `tests\test_env_example.py`.

**Checkpoint Criteria:**

- [ ] Invalid config diagnostics come from feature 002 loader/error types.
- [ ] Missing required env vars are reported using names matching `.env.example`.
- [ ] `.env.example` contains placeholders only and no real secrets.
- [ ] Output states config changes require restarting both deployables.
- [ ] No file watcher, hot reload, or automatic repository discovery is introduced.

**Context Notes:**

- Dependencies: feature 002 intent contracts.
- Architecture anchors: `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#deployment`.
- Estimated complexity: Medium.

### Slice 3: GitHub App installation and permission verification

**Scope:** Add GitHub App installation validation through feature 003's GitHub provider/client seam. Verify installation id, repository access, default branch/repo id consistency where available, and permission requirements derived from publication policy.

**User Stories:** US-2, US-4

**Automation:** HITL

**Automation Reason:** This slice validates a security/permission boundary and must avoid duplicate GitHub API paths.

**Deliverables:**

- Provider-level method or onboarding adapter function such as `verify_installation(repository_config)` returning safe installation metadata.
- Permission helper mapping `adr_publication_policy` to required GitHub App permissions.
- Fake GitHub client fixtures for installed, missing, suspended, wrong-repo, read-only, and write-required cases.
- `tests\onboarding\test_github_installation_validation.py`.

**Checkpoint Criteria:**

- [ ] Valid installation and required permissions produce passing diagnostics.
- [ ] Missing/wrong/suspended installation fails with repository-scoped remediation.
- [ ] `livingadr_only` requires `contents:read` only.
- [ ] GitHub publication policies require `contents:write`.
- [ ] GitHub API details remain inside the SCM adapter/provider seam.
- [ ] Tests do not require live GitHub network access.

**Context Notes:**

- Dependencies: feature 003 intent contracts.
- Architecture anchors: `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#anti-patterns`.
- Estimated complexity: Medium.

### Slice 4: Operator command/startup check integration

**Scope:** Expose the validation service as a thin CLI command or documented startup check and add command-level tests for pass/fail output and exit codes.

**User Stories:** US-1, US-4

**Automation:** AFK

**Automation Reason:** The behavior is already implemented behind service seams; wrapper should remain thin and deterministic.

**Deliverables:**

- `src\living_adr\cli.py` or app-specific CLI/startup flag wiring.
- Command docs/help text that names the check and expected next steps.
- `tests\onboarding\test_cli_onboarding.py` or equivalent command-runner tests.

**Checkpoint Criteria:**

- [ ] Passing validation exits 0 and prints repository key, publication policy, installation id, and next step.
- [ ] Blocking validation exits non-zero and prints grouped diagnostics.
- [ ] CLI/startup wrapper contains no YAML parsing or direct GitHub API logic.
- [ ] Output labels the check as PoC single-repo onboarding validation and excludes multi-repo automation.

**Context Notes:**

- Estimated complexity: Low.

## Dependency Flow

1. Slice 1 must land first because every later slice emits diagnostics.
2. Slice 2 binds feature 002 and `.env.example` before live GitHub checks.
3. Slice 3 binds feature 003's GitHub provider and permission checks.
4. Slice 4 exposes the behavior to operators.

## Parallelization Notes

Limited parallelism is intentional because all slices share the same validation service. Within implementation, tests for `.env.example` and diagnostic redaction can be authored independently after Slice 1, but slice-level execution should remain mostly serial to avoid churn in command output contracts.
