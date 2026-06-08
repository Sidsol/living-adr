# Task Breakdown: llamaindex-property-graph-adapter

## Legend

- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ⬜ Not started | 🔵 In progress | ✅ Done | ❌ Blocked
- Tasks follow TDD behavior ordering: RED test first, GREEN implementation next, then conformance/verification.

## Tasks by Story

### US-1: Persist a repository-scoped property graph

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | RED: Add persistence initialization tests for repository-safe paths, reopen behavior, and no public LlamaIndex leakage. | ⬜ | First task; also supports US-3. |
| TASK-003 | P1 | GREEN: Implement `LlamaIndexPropertyGraphAdapter` skeleton behind feature 006 port method names. | ⬜ | Depends on TASK-002. |
| TASK-004 | P1 | Export the adapter from `src\living_adr\graph\__init__.py` without exporting internals. | ⬜ | Depends on TASK-003. |
| TASK-005 | P1 | RED: Add repository-isolation tests for same identifiers in different repositories. | ⬜ | Depends on TASK-004; also supports US-2. |
| TASK-007 | P1 | GREEN: Add repository metadata and filtering utilities to the adapter. | ⬜ | Depends on TASK-006. |
| TASK-011 | P1 | RED: Add write behavior tests for ADR upsert, relationships, structural change, supersede/retract, reopen, and rollback. | ⬜ | Depends on TASK-010; also supports US-3/US-4. |
| TASK-012 | P1 | GREEN: Implement write-side graph port methods with repository scope and idempotent persistence. | ⬜ | Depends on TASK-011. |

### US-2: Record schema-version metadata and migrations

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-005 | P1 | RED: Add schema metadata tests for current version, missing metadata, unsupported versions, and repository isolation. | ⬜ | Shared with US-1. |
| TASK-006 | P1 | GREEN: Implement `src\living_adr\graph\schema.py` with schema version, metadata DTOs, allowed labels, migration mapping, and errors. | ⬜ | Depends on TASK-005. |
| TASK-007 | P1 | GREEN: Implement `current_schema_version` and `migrate_schema` in the adapter. | ⬜ | Depends on TASK-006. |
| TASK-019 | P1 | Implement `check_conformance(repository)` diagnostics for schema mismatch and other graph health failures. | ⬜ | Depends on TASK-018. |

### US-3: Maintain SQLite/WAL-compatible local persistence

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | RED: Cover local graph root behavior and reopen semantics under `var\graph`. | ⬜ | Shared with US-1. |
| TASK-002 | P1 | GREEN: Implement `src\living_adr\graph\persistence.py` with graph root config, repository path derivation, open mode, and WAL/same-host documentation. | ⬜ | Depends on TASK-001. |
| TASK-011 | P1 | RED: Add persistence tests proving failed writes do not expose partially current projections. | ⬜ | Depends on TASK-010. |
| TASK-013 | P1 | GREEN: Implement `rebuild_snapshot(repository, at_revision=None)` as the write-side snapshot hook. | ⬜ | Depends on TASK-012. |

### US-4: Preserve provenance for extracted entities and edges

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-008 | P1 | RED: Add validation tests for missing provenance, unsupported labels, repository mismatch, and unsupported extracted path handling. | ⬜ | Depends on TASK-007; also supports US-7. |
| TASK-009 | P1 | GREEN: Implement `src\living_adr\graph\provenance.py` with provenance DTOs, metadata keys, validators, and errors. | ⬜ | Depends on TASK-008. |
| TASK-010 | P1 | GREEN: Implement `src\living_adr\graph\llamaindex_mapping.py` to map domain records/edges to validated internal graph payloads. | ⬜ | Depends on TASK-009. |
| TASK-012 | P1 | GREEN: Persist provenance metadata through write-side adapter methods. | ⬜ | Depends on TASK-011. |

### US-5: Provide read snapshots for MCP context delivery

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-014 | P1 | RED: Add query/snapshot tests for `fetch_adr`, `list_adrs`, `traverse_from_code_area`, `answer_why`, and `validate_snapshot_current`. | ⬜ | Depends on TASK-013. |
| TASK-015 | P1 | GREEN: Implement `src\living_adr\graph\snapshots.py` with current/stale comparison and logical revision handling. | ⬜ | Depends on TASK-014. |
| TASK-016 | P1 | GREEN: Implement read query methods returning only 006 domain DTOs with citations and bounded results. | ⬜ | Depends on TASK-015. |
| TASK-023 | P1 | Verify public boundaries expose no LlamaIndex objects through read DTOs or port signatures. | ⬜ | Depends on TASK-021 and TASK-022. |

### US-6: Pass the feature 006 adapter conformance suite

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-017 | P1 | Wire `tests\graph\test_llamaindex_adapter_conformance.py` to feature 006's conformance suite with a real adapter fixture. | ⬜ | Depends on TASK-016. |
| TASK-018 | P1 | Fix conformance failures without weakening or redefining the feature 006 suite. | ⬜ | Depends on TASK-017. |
| TASK-021 | P1 | Run `uv run pytest` after all implementation tasks land. | ⬜ | Verification; may run with TASK-022. |
| TASK-022 | P1 | Run `uv run ruff check` after all implementation tasks land. | ⬜ | Verification; may run with TASK-021. |

### US-7: Mitigate graph drift and false edges

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-008 | P1 | RED: Add invalid-edge and unsupported-label tests before implementing validation. | ⬜ | Shared with US-4. |
| TASK-010 | P1 | GREEN: Enforce schema-constrained mapping for entities and relationships. | ⬜ | Depends on TASK-009. |
| TASK-019 | P1 | GREEN: Add conformance diagnostics for missing provenance, schema mismatch, orphan edges, unsupported labels, and repository mismatch. | ⬜ | Depends on TASK-018. |
| TASK-020 | P1 | RED/GREEN: Complete validation tests for `check_conformance` named failures and import-boundary checks. | ⬜ | Depends on TASK-019. |

## Infrastructure / Cross-Cutting

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-002 | P1 | Implement graph persistence helper under `src\living_adr\graph\persistence.py`. | ⬜ | Shared infrastructure for all slices. |
| TASK-021 | P1 | Run project tests with existing command `uv run pytest`. | ⬜ | No new test runner. |
| TASK-022 | P1 | Run lint with existing command `uv run ruff check`. | ⬜ | No new lint tool. |
| TASK-023 | P1 | Confirm adapter/core public boundary and no backend leakage. | ⬜ | Final manual/static verification. |

## Execution Order

1. **Behavior A — persistence skeleton:** TASK-001 → TASK-002 → TASK-003 → TASK-004.
2. **Behavior B — repository/schema governance:** TASK-005 → TASK-006 → TASK-007.
3. **Behavior C — provenance/validation:** TASK-008 → TASK-009 → TASK-010.
4. **Behavior D — write port:** TASK-011 → TASK-012 → TASK-013.
5. **Behavior E — read snapshots/query:** TASK-014 → TASK-015 → TASK-016.
6. **Behavior F — conformance:** TASK-017 → TASK-018.
7. **Behavior G — diagnostics/final checks:** TASK-019 → TASK-020 → (TASK-021 and TASK-022 in parallel) → TASK-023.

## Parallel Opportunities

- TASK-021 and TASK-022 can run independently after TASK-020.
- Slice 3 review can begin after Slice 2 while Slice 4 planning context is prepared, but write tasks should remain sequential because validation and provenance are prerequisites for safe persistence.
- No implementation tasks should modify feature 006 contracts in parallel with this work.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 23 | 5-7 focused implementation sessions |
| P2 | 0 | 0 |
| P3 | 0 | 0 |