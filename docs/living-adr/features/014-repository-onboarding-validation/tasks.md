# Task Breakdown: repository-onboarding-validation

## Legend

- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ⬜ Not started | 🔵 In progress | ✅ Done | ❌ Blocked
- Tasks follow TDD behavior ordering: RED test first, GREEN implementation next, then integration/export where needed.

## Tasks by Story

### US-1: Run a repository onboarding validation check

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | RED: Add diagnostic aggregation tests for pass/fail status, category grouping, remediation text, and exit-code mapping. | ✅ | First task; supports all stories. |
| TASK-002 | P1 | GREEN: Implement onboarding diagnostic models, category/severity enums, result aggregation, formatter, and exit-code helper. | ✅ | Depends on TASK-001. |
| TASK-007 | P1 | RED: Add validation-service tests proving config is loaded through feature 002 loader and invalid config diagnostics are preserved. | ✅ | Depends on TASK-002. |
| TASK-008 | P1 | GREEN: Implement `OnboardingValidator` config-loading path using feature 002 contracts; no YAML parsing in onboarding. | ✅ | Depends on TASK-007. |
| TASK-017 | P1 | RED: Add CLI/startup-check tests for success and blocking-failure exit behavior. | ✅ | Depends on TASK-016. |
| TASK-018 | P1 | GREEN: Wire `living-adr onboard validate` or equivalent startup-check flag as a thin wrapper over `OnboardingValidator`. | ✅ | Depends on TASK-017. |

### US-2: Verify GitHub App installation for the configured repository

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-011 | P1 | RED: Add fake-provider tests for valid GitHub App installation, repository access, installation id mismatch, missing installation, suspended installation, and wrong repository. | ✅ | Depends on TASK-008. |
| TASK-012 | P1 | GREEN: Add/expose fakeable GitHub provider installation verification result using feature 003 provider/client seam. | ✅ | Depends on TASK-011. |
| TASK-013 | P1 | RED: Add permission-policy tests for `livingadr_only` requiring `contents:read` and publish policies requiring `contents:write`. | ✅ | Depends on TASK-012. |
| TASK-014 | P1 | GREEN: Implement permission mapping and convert missing permissions into blocking onboarding diagnostics. | ✅ | Depends on TASK-013. |
| TASK-015 | P1 | Integrate GitHub installation and permission verification into `OnboardingValidator` for each configured `RepositoryConfig`. | ✅ | Depends on TASK-014. |

### US-3: Align examples and diagnostics with required environment/config inputs

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-004 | P1 | RED: Add redaction tests covering private key paths/content, webhook secret, API keys, LangSmith key, UI token, raw payload, diff, prompt, draft, and reviewer comments. | ✅ | Depends on TASK-002. |
| TASK-005 | P1 | GREEN: Implement formatter redaction/allowlist so diagnostics print only safe metadata. | ✅ | Depends on TASK-004. |
| TASK-009 | P1 | RED: Add environment validation tests for missing required variables and placeholder-only `.env.example` alignment. | ✅ | Depends on TASK-008. |
| TASK-010 | P1 | GREEN: Implement required environment registry, environment presence checks, `.env.example` placeholders, and drift test support. | ✅ | Depends on TASK-009. |

### US-4: Surface operator diagnostics without broad governance automation

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-003 | P1 | RED: Add tests proving diagnostics can include safe repository metadata but never raw webhook payloads, diffs, prompts, drafts, or secrets. | ✅ | Depends on TASK-002; may be combined with TASK-004 if desired. |
| TASK-006 | P1 | Add diagnostic categories for config, environment, GitHub App, permissions, webhook/replay prerequisite, and lifecycle. | ✅ | Depends on TASK-005. |
| TASK-016 | P1 | Add lifecycle and scope diagnostics stating restart-required semantics and no multi-repo governance automation/hot reload. | ✅ | Depends on TASK-015. |
| TASK-019 | P2 | Add command help or existing operator-doc snippet describing the validation check, pass/fail output, and next steps. | ✅ | Depends on TASK-018; update docs only if repo has an existing doc location. |

## Infrastructure / Cross-Cutting

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-020 | P1 | Run existing focused onboarding tests after each slice. | ✅ | Verification only. |
| TASK-021 | P1 | Run full existing test suite, expected `uv run pytest` if project scaffold uses uv/pytest. | ✅ | Verification only. |
| TASK-022 | P1 | Run existing lint command, expected `uv run ruff check` if configured. | ✅ | Verification only. |
| TASK-023 | P1 | Review code for forbidden scope: no hot reload/watchers, no automatic repo discovery, no auto-installing GitHub App, no direct GitHub API calls outside provider seam, no secrets in logs/examples. | ✅ | Final self-review. |

## Execution Order

1. **Diagnostics base:** TASK-001 → TASK-002 → TASK-003/TASK-004 → TASK-005 → TASK-006.
2. **Config/env path:** TASK-007 → TASK-008 → TASK-009 → TASK-010.
3. **GitHub verification path:** TASK-011 → TASK-012 → TASK-013 → TASK-014 → TASK-015.
4. **Lifecycle/scope and command:** TASK-016 → TASK-017 → TASK-018 → TASK-019.
5. **Verification:** TASK-020 → TASK-021 → TASK-022 → TASK-023.

## Parallel Opportunities

- TASK-003 and TASK-004 can be authored together after TASK-002.
- TASK-009 `.env.example` drift tests can be drafted while TASK-011 GitHub fake-provider tests are drafted, once TASK-008 defines validator injection points.
- Verification tasks may run independently after all implementation tasks complete if CI supports parallel jobs.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 22 | 2-3 focused implementation sessions |
| P2 | 1 | Small documentation follow-up |
| P3 | 0 | 0 |

