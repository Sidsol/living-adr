# Task Breakdown: graph-store-ports-and-approval-seam

## Legend

- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ⬜ Not started | 🔵 In progress | ✅ Done | ❌ Blocked
- Tasks follow TDD behavior ordering: RED test first, GREEN implementation next, then integration/export/verification.

## Tasks by Story

### US-1: Define graph value objects

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | RED: Add graph model tests for IDs, edges, relationship labels, snapshots, schema versions, query DTOs, repository scope, and provenance. | ✅ | First task. |
| TASK-002 | P1 | GREEN: Implement immutable graph value objects in `src\living_adr\core\graph\models.py`. | ✅ | Depends on TASK-001. |
| TASK-003 | P1 | Export graph value objects from `src\living_adr\core\graph\__init__.py`. | ✅ | Depends on TASK-002. |

### US-2: Define ADR record repository expectations

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-004 | P1 | RED: Add ADR record tests for repository scope, approved decision linkage, status, content hash/provenance, and projection conflict behavior. | ✅ | Depends on TASK-003. |
| TASK-005 | P1 | GREEN: Implement `ADRStatus`, `ADRRecord`, and `ADRRecordRepository` in `src\living_adr\core\adr.py`. | ✅ | Depends on TASK-004. |
| TASK-006 | P1 | Document/encode source hierarchy in `ADRRecordRepository`: evidence → approved ADR record → graph projection. | ✅ | Depends on TASK-005. |

### US-3: Define write and read ports

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-007 | P1 | RED: Add port signature tests requiring repository and decision on writes and repository on reads. | ✅ | Depends on TASK-006. |
| TASK-008 | P1 | GREEN: Implement `ArchitectureGraphStore` and `ArchitectureContextQuery` Protocols using domain types only. | ✅ | Depends on TASK-007. |
| TASK-009 | P1 | Export graph port contracts from `src\living_adr\core\graph\__init__.py`. | ✅ | Depends on TASK-008. |

### US-4: Enforce approval-bound graph mutation

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-010 | P1 | RED: Add tests proving invalid approval inputs raise before any fake adapter call. | ✅ | Depends on TASK-009. |
| TASK-011 | P1 | GREEN: Implement `ApprovedReviewDecision` and approval boundary errors in `src\living_adr\core\approval.py`. | ✅ | Landed with slice 3 (ports depend on it). |
| TASK-012 | P1 | GREEN: Implement `ApprovalBoundMutationService` facade and mutation request DTOs. | ✅ | Depends on TASK-011. |
| TASK-013 | P1 | RED/GREEN: Add valid delegation and metadata-only observability tests for the service. | ✅ | Depends on TASK-012. |

### US-5: Provide adapter conformance surface

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-014 | P1 | RED: Create reusable conformance suite skeleton for repository scoping, approval-required writes, read-only query behavior, and no concrete leaks. | ✅ | Depends on TASK-013. |
| TASK-015 | P1 | GREEN: Implement in-memory graph store/query fake for conformance and service tests. | ✅ | Depends on TASK-014. |
| TASK-016 | P1 | GREEN: Add test that runs conformance suite against the in-memory adapter and documents adapter opt-in. | ✅ | Depends on TASK-015. |
| TASK-017 | P1 | Add negative conformance helpers for repository-scope bypass, approval bypass, and backend-object leakage. | ✅ | Depends on TASK-016. |

### US-6: Preserve dependency and source-of-truth boundaries

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-018 | P1 | Add import-boundary tests ensuring core graph/ADR/approval modules import no LlamaIndex, LangSmith, FastAPI, MCP, DB, or adapter modules. | ✅ | Depends on TASK-017. |
| TASK-019 | P1 | Export top-level core contracts from `src\living_adr\core\__init__.py` if package conventions require it. | ✅ | Depends on TASK-018. |
| TASK-022 | P1 | Confirm public port signatures expose only LivingADR domain values and standard scalar/collection types. | ✅ | Depends on TASK-019. |

## Infrastructure / Cross-Cutting

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-020 | P1 | Run `uv run pytest` after all implementation tasks land. | ✅ | 219 passed (170 baseline + 49 new). |
| TASK-021 | P1 | Run `uv run ruff check` after all implementation tasks land. | ✅ | All checks passed. |

## Execution Order

1. **Sequential behavior A — graph vocabulary:** TASK-001 → TASK-002 → TASK-003.
2. **Sequential behavior B — ADR authority:** TASK-004 → TASK-005 → TASK-006.
3. **Sequential behavior C — ports:** TASK-007 → TASK-008 → TASK-009.
4. **Sequential behavior D — approval boundary:** TASK-010 → TASK-011 → TASK-012 → TASK-013.
5. **Sequential behavior E — conformance:** TASK-014 → TASK-015 → TASK-016 → TASK-017.
6. **Sequential behavior F — integration boundaries:** TASK-018 → TASK-019 → TASK-022.
7. **Verification:** TASK-020 and TASK-021 may run in parallel after TASK-019.

## Parallel Opportunities

- TASK-020 and TASK-021 can run independently after implementation is complete.
- Future implementation may split review of tests from code, but write tasks are intentionally mostly sequential because each slice stabilizes contracts consumed by the next slice.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 22 | 3-5 focused implementation sessions |
| P2 | 0 | 0 |
| P3 | 0 | 0 |
