# Implementation Plan: llamaindex-property-graph-adapter

## Technical Context

- Language/Framework: Python 3.12, `living_adr.graph` adapter package inside the `living-adr` repository.
- Key Dependencies: feature 006 graph ports/value objects/conformance suite; feature 002 `RepositoryIdentity`; LlamaIndex 0.14.22; SQLite/WAL-compatible local persistence where SQLite state is used.
- Test Framework: pytest.
- Build System: uv with `pyproject.toml`; lint/format via Ruff.
- Architecture anchors: `..\..\architecture.md#tech-stack`, `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#deployment`.

## Project Structure

```text
living-adr\
├── src\living_adr\
│   ├── graph\
│   │   ├── __init__.py                         ← CREATE: default adapter exports
│   │   ├── llamaindex_adapter.py               ← CREATE: implements 006 graph ports
│   │   ├── llamaindex_mapping.py               ← CREATE: domain ↔ LlamaIndex mapping
│   │   ├── persistence.py                      ← CREATE: var\graph paths/open modes
│   │   ├── provenance.py                       ← CREATE: provenance DTOs/validation
│   │   ├── schema.py                           ← CREATE: graph schema version/labels
│   │   └── snapshots.py                        ← CREATE: read snapshot references
│   └── core\graph\ports.py                     ← READ ONLY: consume feature 006 ports
├── tests\
│   ├── graph\
│   │   ├── test_llamaindex_adapter_conformance.py  ← CREATE
│   │   ├── test_llamaindex_adapter_persistence.py  ← CREATE
│   │   ├── test_llamaindex_adapter_queries.py      ← CREATE
│   │   └── test_llamaindex_adapter_validation.py   ← CREATE
│   └── conformance\graph_store_conformance.py      ← READ ONLY: suite from feature 006
└── var\graph\                                  ← RUNTIME ONLY: not committed
```

## Implementation Phases

### Phase 1: Adapter skeleton and persistence root

#### Step 1.1: RED persistence path and initialization tests
- **Task ID:** TASK-001
- **File:** `tests\graph\test_llamaindex_adapter_persistence.py`
- **Action:** Create
- **Changes:** Test deterministic repository-safe path derivation under `var\graph`, path traversal rejection, adapter initialize/reopen behavior, and absence of public LlamaIndex/storage-context attributes.

#### Step 1.2: Implement persistence helper
- **Task ID:** TASK-002
- **File:** `src\living_adr\graph\persistence.py`
- **Action:** Create
- **Changes:** Add graph root config, repository key normalization/hash, storage directory creation, open-mode enum, and same-host/WAL-compatible docstrings.

#### Step 1.3: Implement adapter skeleton
- **Task ID:** TASK-003
- **File:** `src\living_adr\graph\llamaindex_adapter.py`
- **Action:** Create
- **Changes:** Add `LlamaIndexPropertyGraphAdapter` constructor, persistence dependency injection, internal LlamaIndex initialization/load stubs, and explicit implementation of 006 port method names raising controlled `NotImplementedError` until later slices.

#### Step 1.4: Export adapter package
- **Task ID:** TASK-004
- **File:** `src\living_adr\graph\__init__.py`
- **Action:** Create
- **Changes:** Export `LlamaIndexPropertyGraphAdapter` and persistence config without exporting LlamaIndex internals.

### Phase 2: Repository isolation and schema metadata

#### Step 2.1: RED schema and isolation tests
- **Task ID:** TASK-005
- **File:** `tests\graph\test_llamaindex_adapter_validation.py`
- **Action:** Create
- **Changes:** Test `current_schema_version`, initial schema metadata creation, unsupported/missing schema behavior, and same identifier isolation across two repositories.

#### Step 2.2: Implement graph schema module
- **Task ID:** TASK-006
- **File:** `src\living_adr\graph\schema.py`
- **Action:** Create
- **Changes:** Define adapter schema version constant, metadata DTO, allowed entity/relationship labels mapped from 006 `RelationshipType`, migration status mapping, and schema validation errors.

#### Step 2.3: Implement schema metadata methods
- **Task ID:** TASK-007
- **File:** `src\living_adr\graph\llamaindex_adapter.py`
- **Action:** Modify
- **Changes:** Implement `current_schema_version`, `migrate_schema`, repository metadata read/write, and repository-scope filtering utilities.

### Phase 3: Provenance and relationship validation

#### Step 3.1: RED provenance and invalid-edge tests
- **Task ID:** TASK-008
- **File:** `tests\graph\test_llamaindex_adapter_validation.py`
- **Action:** Modify
- **Changes:** Add tests for missing ADR/evidence/decision/extraction provenance, unsupported relationship labels, repository mismatch, and quarantine/rejection of unsupported extracted paths.

#### Step 3.2: Implement provenance module
- **Task ID:** TASK-009
- **File:** `src\living_adr\graph\provenance.py`
- **Action:** Create
- **Changes:** Add provenance DTOs, completeness validators, metadata key constants, and errors for missing or mismatched provenance.

#### Step 3.3: Implement LlamaIndex mapping module
- **Task ID:** TASK-010
- **File:** `src\living_adr\graph\llamaindex_mapping.py`
- **Action:** Create
- **Changes:** Map 006 domain `ADRRecord`, `GraphEdge`, `StructuralChange`, and provenance into internal property graph node/relationship payloads; validate allowed labels before persistence.

### Phase 4: Write-side port implementation

#### Step 4.1: RED write behavior tests
- **Task ID:** TASK-011
- **File:** `tests\graph\test_llamaindex_adapter_persistence.py`
- **Action:** Modify
- **Changes:** Add tests for `upsert_adr_node`, `add_relationship`, `record_structural_change`, `supersede_adr`, `retract_adr`, reopen after write, rollback/partial-write failure, and persisted provenance.

#### Step 4.2: Implement core write methods
- **Task ID:** TASK-012
- **File:** `src\living_adr\graph\llamaindex_adapter.py`
- **Action:** Modify
- **Changes:** Implement 006 `ArchitectureGraphStore` write methods using mapping/provenance/schema helpers, repository filters, idempotent node/edge upsert semantics, and controlled adapter errors.

#### Step 4.3: Implement snapshot rebuild hook
- **Task ID:** TASK-013
- **File:** `src\living_adr\graph\llamaindex_adapter.py`
- **Action:** Modify
- **Changes:** Implement `rebuild_snapshot(repository, at_revision=None)` as a logical current snapshot or persisted snapshot copy, preserving schema/provenance metadata.

### Phase 5: Read snapshots and query DTOs

#### Step 5.1: RED query and snapshot tests
- **Task ID:** TASK-014
- **File:** `tests\graph\test_llamaindex_adapter_queries.py`
- **Action:** Create
- **Changes:** Test `fetch_adr`, `list_adrs`, `traverse_from_code_area`, `answer_why`, `validate_snapshot_current`, bounded results, stale snapshot behavior, citations, and no mutation during reads.

#### Step 5.2: Implement snapshot helper
- **Task ID:** TASK-015
- **File:** `src\living_adr\graph\snapshots.py`
- **Action:** Create
- **Changes:** Add snapshot reference construction, current/stale comparison, logical revision handling, and retryable stale/busy result helpers if represented by 006 DTOs/errors.

#### Step 5.3: Implement read query methods
- **Task ID:** TASK-016
- **File:** `src\living_adr\graph\llamaindex_adapter.py`
- **Action:** Modify
- **Changes:** Implement 006 `ArchitectureContextQuery` methods returning `ADRPath`, `WhyAnswer`, `ProvenancedADR`, and `ADRRef`; enforce repository scope, snapshot option, limits, and citation/provenance output.

### Phase 6: 006 conformance suite green

#### Step 6.1: Wire conformance fixture
- **Task ID:** TASK-017
- **File:** `tests\graph\test_llamaindex_adapter_conformance.py`
- **Action:** Create
- **Changes:** Create repository-local storage fixture and adapter factory for feature 006's conformance suite; document future adapter opt-in pattern.

#### Step 6.2: Run and fix conformance failures
- **Task ID:** TASK-018
- **Files:** `src\living_adr\graph\llamaindex_adapter.py`, `src\living_adr\graph\llamaindex_mapping.py`, `src\living_adr\graph\schema.py`, `src\living_adr\graph\provenance.py`, `src\living_adr\graph\snapshots.py`
- **Action:** Modify
- **Changes:** Fix adapter behavior until repository scoping, approval-required writes, read/write separation, schema hooks, snapshot hooks, and no-backend-leak conformance tests pass without changing the suite.

### Phase 7: Drift diagnostics and final verification

#### Step 7.1: Add conformance diagnostics implementation
- **Task ID:** TASK-019
- **File:** `src\living_adr\graph\llamaindex_adapter.py`
- **Action:** Modify
- **Changes:** Implement `check_conformance(repository)` diagnostics for missing provenance, schema mismatch, orphan edges, unsupported labels, and repository mismatch.

#### Step 7.2: Complete validation tests
- **Task ID:** TASK-020
- **File:** `tests\graph\test_llamaindex_adapter_validation.py`
- **Action:** Modify
- **Changes:** Add final assertions for `check_conformance` named failures and import-boundary expectations that core modules have no LlamaIndex imports.

#### Step 7.3: Run unit tests
- **Task ID:** TASK-021
- **Files:** `tests\graph\*.py`, `tests\conformance\graph_store_conformance.py`
- **Action:** Verify
- **Changes:** Run `uv run pytest` and fix only failures caused by this feature.

#### Step 7.4: Run lint checks
- **Task ID:** TASK-022
- **File:** `pyproject.toml`
- **Action:** Verify
- **Changes:** Run `uv run ruff check` and fix only issues caused by this feature.

#### Step 7.5: Confirm public boundary
- **Task ID:** TASK-023
- **Files:** `src\living_adr\graph\__init__.py`, `src\living_adr\graph\llamaindex_adapter.py`, `src\living_adr\core\graph\ports.py`
- **Action:** Verify
- **Changes:** Confirm public signatures expose only 006 domain values and standard scalars/collections; no LlamaIndex internals cross the port.

## Complexity Tracking

| Phase | Files Changed | New Files | Estimated Effort | Risk |
|---|---:|---:|---|---|
| Phase 1 | 0 | 4 | Medium | Medium |
| Phase 2 | 1 | 1 | Medium | High |
| Phase 3 | 1 | 2 | Medium | High |
| Phase 4 | 2 | 0 | Large | High |
| Phase 5 | 1 | 2 | Large | High |
| Phase 6 | 5 | 1 | Medium | High |
| Phase 7 | 3 | 0 | Low | Medium |

## Dependencies & Prerequisites

- Feature 006 implementation is complete and exposes graph ports, value objects, `ApprovedReviewDecision`, `ApprovalBoundMutationService`, and conformance suite.
- Feature 002 implementation provides `RepositoryIdentity` and configuration conventions.
- `llama-index==0.14.22` is installed by the project scaffold.
- No external graph database is required.
- Runtime graph files under `var\graph` are not committed; tests must use repo-local test fixture directories and clean them up.

## Rollback Strategy

All changes are additive in the `living_adr.graph` package and `tests\graph`. If a phase fails, remove files introduced by that phase and revert adapter modifications from that phase. Since no committed production migrations or external services are introduced, rollback is file-level plus deletion of local runtime test data under project-local fixture paths.

## Machine-Readable Task Graph

```yaml
task_graph:
  - id: TASK-001
    slice: 1
    story: US-1/US-3
    depends_on: []
    parallelizable_with: []
    files: [tests\graph\test_llamaindex_adapter_persistence.py]
  - id: TASK-002
    slice: 1
    story: US-3
    depends_on: [TASK-001]
    parallelizable_with: []
    files: [src\living_adr\graph\persistence.py]
  - id: TASK-003
    slice: 1
    story: US-1
    depends_on: [TASK-002]
    parallelizable_with: []
    files: [src\living_adr\graph\llamaindex_adapter.py]
  - id: TASK-004
    slice: 1
    story: US-1
    depends_on: [TASK-003]
    parallelizable_with: []
    files: [src\living_adr\graph\__init__.py]
  - id: TASK-005
    slice: 2
    story: US-1/US-2
    depends_on: [TASK-004]
    parallelizable_with: []
    files: [tests\graph\test_llamaindex_adapter_validation.py]
  - id: TASK-006
    slice: 2
    story: US-2
    depends_on: [TASK-005]
    parallelizable_with: []
    files: [src\living_adr\graph\schema.py]
  - id: TASK-007
    slice: 2
    story: US-1/US-2
    depends_on: [TASK-006]
    parallelizable_with: []
    files: [src\living_adr\graph\llamaindex_adapter.py]
  - id: TASK-008
    slice: 3
    story: US-4/US-7
    depends_on: [TASK-007]
    parallelizable_with: []
    files: [tests\graph\test_llamaindex_adapter_validation.py]
  - id: TASK-009
    slice: 3
    story: US-4
    depends_on: [TASK-008]
    parallelizable_with: []
    files: [src\living_adr\graph\provenance.py]
  - id: TASK-010
    slice: 3
    story: US-7
    depends_on: [TASK-009]
    parallelizable_with: []
    files: [src\living_adr\graph\llamaindex_mapping.py]
  - id: TASK-011
    slice: 4
    story: US-1/US-3/US-4
    depends_on: [TASK-010]
    parallelizable_with: []
    files: [tests\graph\test_llamaindex_adapter_persistence.py]
  - id: TASK-012
    slice: 4
    story: US-1/US-4
    depends_on: [TASK-011]
    parallelizable_with: []
    files: [src\living_adr\graph\llamaindex_adapter.py]
  - id: TASK-013
    slice: 4
    story: US-3
    depends_on: [TASK-012]
    parallelizable_with: []
    files: [src\living_adr\graph\llamaindex_adapter.py]
  - id: TASK-014
    slice: 5
    story: US-5
    depends_on: [TASK-013]
    parallelizable_with: []
    files: [tests\graph\test_llamaindex_adapter_queries.py]
  - id: TASK-015
    slice: 5
    story: US-5
    depends_on: [TASK-014]
    parallelizable_with: []
    files: [src\living_adr\graph\snapshots.py]
  - id: TASK-016
    slice: 5
    story: US-5
    depends_on: [TASK-015]
    parallelizable_with: []
    files: [src\living_adr\graph\llamaindex_adapter.py]
  - id: TASK-017
    slice: 6
    story: US-6
    depends_on: [TASK-016]
    parallelizable_with: []
    files: [tests\graph\test_llamaindex_adapter_conformance.py]
  - id: TASK-018
    slice: 6
    story: US-6
    depends_on: [TASK-017]
    parallelizable_with: []
    files: [src\living_adr\graph\llamaindex_adapter.py, src\living_adr\graph\llamaindex_mapping.py, src\living_adr\graph\schema.py, src\living_adr\graph\provenance.py, src\living_adr\graph\snapshots.py]
  - id: TASK-019
    slice: 7
    story: US-2/US-7
    depends_on: [TASK-018]
    parallelizable_with: []
    files: [src\living_adr\graph\llamaindex_adapter.py]
  - id: TASK-020
    slice: 7
    story: US-7
    depends_on: [TASK-019]
    parallelizable_with: []
    files: [tests\graph\test_llamaindex_adapter_validation.py]
  - id: TASK-021
    slice: 7
    story: verification
    depends_on: [TASK-020]
    parallelizable_with: [TASK-022]
    files: [tests\graph\test_llamaindex_adapter_conformance.py, tests\graph\test_llamaindex_adapter_persistence.py, tests\graph\test_llamaindex_adapter_queries.py, tests\graph\test_llamaindex_adapter_validation.py]
  - id: TASK-022
    slice: 7
    story: verification
    depends_on: [TASK-020]
    parallelizable_with: [TASK-021]
    files: [pyproject.toml]
  - id: TASK-023
    slice: 7
    story: verification
    depends_on: [TASK-021, TASK-022]
    parallelizable_with: []
    files: [src\living_adr\graph\__init__.py, src\living_adr\graph\llamaindex_adapter.py, src\living_adr\core\graph\ports.py]
```