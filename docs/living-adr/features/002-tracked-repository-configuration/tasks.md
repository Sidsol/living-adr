# Task Breakdown: tracked-repository-configuration

## Legend

- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ⬜ Not started | 🔵 In progress | ✅ Done | ❌ Blocked
- Tasks follow TDD behavior ordering: RED test first, GREEN implementation next, then integration/export where needed.

## Tasks by Story

### US-1: Load tracked repository configuration

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-003 | P1 | RED: Add tests for `LivingADRConfig.repositories`, `N>=1`, duplicate identity rejection, and no secret-bearing fields. | ✅ | Depends on TASK-002. |
| TASK-004 | P1 | GREEN: Implement `RepositoryConfig` and `LivingADRConfig` with list validation and duplicate canonical key checks. | ✅ | Depends on TASK-003. |
| TASK-005 | P1 | Export config contracts from `src\living_adr\core\__init__.py` if package conventions require exports. | ✅ | Depends on TASK-004. |
| TASK-006 | P1 | RED: Add config loader tests for default path, `LIVING_ADR_CONFIG`, missing file, invalid YAML, and validation diagnostics. | ✅ | Depends on TASK-005. |
| TASK-007 | P1 | GREEN: Implement `load_living_adr_config`, path resolution, YAML parsing, and `ConfigStartupError`. | ✅ | Depends on TASK-006. |

### US-2: Validate repository identity and config

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | RED: Add tests for valid `RepositoryIdentity`, canonical key generation, missing fields, and unsafe values. | ✅ | First task. |
| TASK-002 | P1 | GREEN: Implement `RepositoryIdentity` value object in `src\living_adr\core\repository.py`. | ✅ | Depends on TASK-001. |

### US-3: Enforce publication and external-LLM policy from config

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-011 | P1 | RED: Add publication-policy tests for all valid enum values, unknown value rejection, and GitHub publish target validation. | ✅ | Depends on TASK-005. |
| TASK-012 | P1 | GREEN: Implement `PublicationPolicy` enum, `publishes_to_github`, and branch/path validators. | ✅ | Depends on TASK-011. |
| TASK-013 | P1 | RED: Add external LLM egress tests for explicit allow, explicit deny, omitted-value behavior, and repository lookup. | ✅ | Depends on TASK-012. |
| TASK-014 | P1 | GREEN: Require and expose `external_llm_allowed` policy helpers for future Claude adapter enforcement. | ✅ | Depends on TASK-013. |

### US-4: Make lifecycle semantics restart-required

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-008 | P1 | RED: Add startup integration tests proving workflow/MCP startup succeeds with valid config and fails with invalid config. | ✅ | Depends on TASK-007. |
| TASK-009 | P1 | GREEN: Wire workflow service startup to load validated config once and fail readiness on `ConfigStartupError`. | ✅ | Depends on TASK-008. |
| TASK-010 | P1 | GREEN: Wire MCP context server startup to load validated config once before serving tools/resources. | ✅ | Depends on TASK-008; can run after or alongside TASK-009. |
| TASK-015 | P1 | RED: Add lifecycle tests proving file changes after load do not mutate the in-memory config snapshot. | ✅ | Depends on TASK-010 and TASK-014. |
| TASK-016 | P1 | GREEN: Ensure workflow and MCP startup inject a config snapshot rather than parsing per request/tool call. | ✅ | Depends on TASK-015. |
| TASK-017 | P1 | Add `living-adr.config.example.yaml` with non-secret sample values and restart-required comments. | ✅ | Depends on TASK-016. |

### US-5: Establish no-op Observability core port

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-018 | P1 | RED: Add tests for no-op `record_event`, `increment_counter`, `start_span`, exception-path span exit, and no LangSmith dependency. | ✅ | Depends on TASK-005. |
| TASK-019 | P1 | GREEN: Implement `Observability`, `ObservationSpan`, and `NoOpObservability` with default-deny raw export docstrings. | ✅ | Depends on TASK-018. |
| TASK-020 | P1 | Export observability contracts from `src\living_adr\core\__init__.py` if package conventions require exports. | ✅ | Depends on TASK-019. |

## Infrastructure / Cross-Cutting

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-021 | P1 | Run `uv run pytest` after all slices land. | ✅ | Verification only; use existing project test command. |
| TASK-022 | P1 | Run `uv run ruff check` after implementation. | ✅ | Verification only; use existing project lint command. |
| TASK-023 | P1 | Confirm no code path imports LangSmith from `src\living_adr\core\observability.py`. | ✅ | Can be assertion/test or grep during review. |

## Execution Order

1. **Sequential behavior A — repository identity:** TASK-001 → TASK-002.
2. **Sequential behavior B — config collection:** TASK-003 → TASK-004 → TASK-005.
3. **Parallel Group C after TASK-005:**
   - Loader/startup path: TASK-006 → TASK-007 → TASK-008 → TASK-009/TASK-010.
   - Policy path: TASK-011 → TASK-012 → TASK-013 → TASK-014.
   - Observability path: TASK-018 → TASK-019 → TASK-020.
4. **Sequential lifecycle path:** TASK-015 → TASK-016 → TASK-017.
5. **Verification:** TASK-021, TASK-022, TASK-023.

## Parallel Opportunities

- **TASK-009 and TASK-010:** different app startup files after common startup tests are written.
- **TASK-006 and TASK-011 and TASK-018:** separate test files can be authored after core config contracts exist.
- **TASK-007 and TASK-019:** separate implementation files, provided exports in `core\__init__.py` are coordinated.
- **Verification tasks TASK-021 and TASK-022:** can run independently after all implementation tasks complete if CI supports parallel jobs.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 23 | 2-4 focused implementation sessions |
| P2 | 0 | 0 |
| P3 | 0 | 0 |
