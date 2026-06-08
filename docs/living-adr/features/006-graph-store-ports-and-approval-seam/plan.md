# Implementation Plan: graph-store-ports-and-approval-seam

## Technical Context

- Language/Framework: Python 3.12, shared `living_adr.core` package.
- Key Dependencies: feature 002 `RepositoryIdentity` and `Observability`; standard library typing/dataclasses or Pydantic if established by feature 002.
- Test Framework: pytest.
- Build System: uv with `pyproject.toml`; lint/format via Ruff.
- Architecture anchors: `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#anti-patterns`.

## Project Structure

```text
living-adr\
├── src\living_adr\
│   ├── core\
│   │   ├── __init__.py                            ← MODIFY: export stable contracts if package style requires
│   │   ├── adr.py                                 ← CREATE: ADRRecord, ADRStatus, ADRRecordRepository
│   │   ├── approval.py                            ← CREATE: ApprovedReviewDecision contract and validation errors
│   │   └── graph\
│   │       ├── __init__.py                        ← CREATE: graph contract exports
│   │       ├── models.py                          ← CREATE: graph value objects and query DTOs
│   │       ├── ports.py                           ← CREATE: ArchitectureGraphStore and ArchitectureContextQuery
│   │       └── approval_bound_mutation.py         ← CREATE: ApprovalBoundMutationService
└── tests\
    ├── core\
    │   ├── test_adr_records.py                    ← CREATE
    │   └── graph\
    │       ├── test_graph_models.py               ← CREATE
    │       ├── test_graph_ports.py                ← CREATE
    │       ├── test_approval_bound_mutation.py    ← CREATE
    │       └── test_graph_import_boundaries.py    ← CREATE
    ├── conformance\
    │   ├── graph_store_conformance.py             ← CREATE: reusable adapter contract suite
    │   └── test_in_memory_graph_conformance.py    ← CREATE
    └── fakes\
        └── in_memory_graph_store.py               ← CREATE: fake adapter for tests
```

## Implementation Phases

### Phase 1: Core graph value objects

#### Step 1.1: Add graph model tests (RED)
- **Task ID:** TASK-001
- **File:** `tests\core\graph\test_graph_models.py`
- **Action:** Create
- **Changes:** Test valid/invalid `NodeId`, `RelationshipType`, `GraphEdge`, `GraphSnapshotRef`, `SchemaVersion`, `ADRRef`, `ADRPath`, `WhyAnswer`, `ProvenancedADR`, and `ConformanceReport` construction with repository scope and provenance.

#### Step 1.2: Implement graph models (GREEN)
- **Task ID:** TASK-002
- **File:** `src\living_adr\core\graph\models.py`
- **Action:** Create
- **Changes:** Add immutable typed value objects and enums using only core/domain imports; include minimal relationship labels for ADR-to-component, ADR-to-evidence, supersedes, retracts, and structural-change links.

#### Step 1.3: Add graph package exports
- **Task ID:** TASK-003
- **File:** `src\living_adr\core\graph\__init__.py`
- **Action:** Create
- **Changes:** Export graph value objects from stable package path.

### Phase 2: ADR record repository and source hierarchy

#### Step 2.1: Add ADR record tests (RED)
- **Task ID:** TASK-004
- **File:** `tests\core\test_adr_records.py`
- **Action:** Create
- **Changes:** Test repository scope, approved decision linkage, status values, content hash/provenance fields, and projection conflict expectations.

#### Step 2.2: Implement ADR record contract (GREEN)
- **Task ID:** TASK-005
- **File:** `src\living_adr\core\adr.py`
- **Action:** Create
- **Changes:** Add `ADRStatus`, `ADRRecord`, `ADRRecordRepository` Protocol, repository-scoped lookup methods, and source-of-truth docstrings.

#### Step 2.3: Encode source hierarchy expectations
- **Task ID:** TASK-006
- **File:** `src\living_adr\core\adr.py`
- **Action:** Modify
- **Changes:** Add constants/docstrings or typed result values documenting evidence → approved ADR record → graph projection hierarchy and conflict handling.

### Phase 3: Architecture graph read/write ports

#### Step 3.1: Add port signature tests (RED)
- **Task ID:** TASK-007
- **File:** `tests\core\graph\test_graph_ports.py`
- **Action:** Create
- **Changes:** Assert write method signatures require `repository` and `decision`, read method signatures require `repository`, and read port has no mutation method names.

#### Step 3.2: Implement graph ports (GREEN)
- **Task ID:** TASK-008
- **File:** `src\living_adr\core\graph\ports.py`
- **Action:** Create
- **Changes:** Define `ArchitectureGraphStore` and `ArchitectureContextQuery` Protocols matching architecture sketches and using only domain value objects.

#### Step 3.3: Export port contracts
- **Task ID:** TASK-009
- **File:** `src\living_adr\core\graph\__init__.py`
- **Action:** Modify
- **Changes:** Export port Protocols alongside value objects.

### Phase 4: Approval-bound mutation service

#### Step 4.1: Add invalid approval tests (RED)
- **Task ID:** TASK-010
- **File:** `tests\core\graph\test_approval_bound_mutation.py`
- **Action:** Create
- **Changes:** Test `None`, rejected/non-approved outcome, repository mismatch, draft content hash mismatch, and mutation fingerprint mismatch all raise before fake adapter call count changes.

#### Step 4.2: Implement approval contract (GREEN)
- **Task ID:** TASK-011
- **File:** `src\living_adr\core\approval.py`
- **Action:** Create
- **Changes:** Add `ApprovedReviewDecision`, approval outcome enum or literal, and errors such as `ApprovalRequiredError`, `DecisionRepositoryMismatchError`, `DraftContentMismatchError`, and `MutationFingerprintMismatchError`.

#### Step 4.3: Implement mutation service facade (GREEN)
- **Task ID:** TASK-012
- **File:** `src\living_adr\core\graph\approval_bound_mutation.py`
- **Action:** Create
- **Changes:** Add mutation request DTOs and service methods for ADR upsert, relationship add, structural-change record, supersede, retract, and schema migration; validate before delegating to `ArchitectureGraphStore`.

#### Step 4.4: Add valid delegation and observability tests
- **Task ID:** TASK-013
- **File:** `tests\core\graph\test_approval_bound_mutation.py`
- **Action:** Modify
- **Changes:** Test valid approved decision delegates exactly once and emits only metadata fields through feature 002 `Observability` seam.

### Phase 5: Adapter conformance suite

#### Step 5.1: Add conformance suite skeleton (RED)
- **Task ID:** TASK-014
- **File:** `tests\conformance\graph_store_conformance.py`
- **Action:** Create
- **Changes:** Define reusable assertions for repository scoping, approval-required mutations, read-only query semantics, schema version hook, and no concrete persistence leaks.

#### Step 5.2: Add fake adapter fixture
- **Task ID:** TASK-015
- **File:** `tests\fakes\in_memory_graph_store.py`
- **Action:** Create
- **Changes:** Implement in-memory `ArchitectureGraphStore`/`ArchitectureContextQuery` test double using domain values only and call counters for invalid mutation checks.

#### Step 5.3: Prove conformance suite executes (GREEN)
- **Task ID:** TASK-016
- **File:** `tests\conformance\test_in_memory_graph_conformance.py`
- **Action:** Create
- **Changes:** Run the reusable conformance suite against the in-memory adapter and document adapter opt-in pattern for feature 007.

#### Step 5.4: Add negative conformance examples
- **Task ID:** TASK-017
- **File:** `tests\conformance\graph_store_conformance.py`
- **Action:** Modify
- **Changes:** Include helper assertions that fail adapters ignoring repository scope, bypassing approval, or returning backend objects.

### Phase 6: Integration exports and verification

#### Step 6.1: Add import-boundary tests
- **Task ID:** TASK-018
- **File:** `tests\core\graph\test_graph_import_boundaries.py`
- **Action:** Create
- **Changes:** Assert core ADR/approval/graph modules do not import LlamaIndex, LangSmith, FastAPI, MCP, SQLite connection classes, or concrete adapter modules.

#### Step 6.2: Export top-level core contracts
- **Task ID:** TASK-019
- **File:** `src\living_adr\core\__init__.py`
- **Action:** Modify
- **Changes:** Export `ADRRecord`, `ADRRecordRepository`, `ApprovedReviewDecision`, graph ports, and mutation service if package conventions expose core contracts here.

#### Step 6.3: Run unit tests
- **Task ID:** TASK-020
- **Files:** `tests\core\test_adr_records.py`, `tests\core\graph\*.py`, `tests\conformance\*.py`
- **Action:** Verify
- **Changes:** Run `uv run pytest` and fix only failures caused by this feature.

#### Step 6.4: Run lint checks
- **Task ID:** TASK-021
- **File:** `pyproject.toml`
- **Action:** Verify
- **Changes:** Run `uv run ruff check` and fix only issues caused by this feature.

#### Step 6.5: Confirm no persistence leakage
- **Task ID:** TASK-022
- **Files:** `src\living_adr\core\graph\ports.py`, `src\living_adr\core\graph\models.py`, `src\living_adr\core\graph\approval_bound_mutation.py`
- **Action:** Verify
- **Changes:** Confirm public signatures expose only LivingADR domain values and standard collection/scalar types.

## Complexity Tracking

| Phase | Files Changed | New Files | Estimated Effort | Risk |
|---|---:|---:|---|---|
| Phase 1 | 1 | 3 | Medium | Medium |
| Phase 2 | 0 | 2 | Medium | High |
| Phase 3 | 1 | 2 | Medium | High |
| Phase 4 | 1 | 3 | Medium | High |
| Phase 5 | 0 | 4 | Medium | Medium |
| Phase 6 | 1 | 1 | Low | Low |

## Dependencies & Prerequisites

- Feature 002 `RepositoryIdentity` and `Observability` contracts are available or implemented first.
- No new runtime dependencies are expected; use existing Python typing/Pydantic conventions from feature 002.
- Durable approval/audit behavior remains a downstream feature 010 responsibility.

## Rollback Strategy

Each phase is additive. If a phase fails, revert newly created core/test files from that phase and remove any exports added in `src\living_adr\core\__init__.py` or `src\living_adr\core\graph\__init__.py`. Because no production persistence migrations are introduced, rollback is file-level only.

## Machine-Readable Task Graph

```yaml
task_graph:
  - id: TASK-001
    slice: 1
    story: US-1
    depends_on: []
    parallelizable_with: []
    files: [tests\core\graph\test_graph_models.py]
  - id: TASK-002
    slice: 1
    story: US-1
    depends_on: [TASK-001]
    parallelizable_with: []
    files: [src\living_adr\core\graph\models.py]
  - id: TASK-003
    slice: 1
    story: US-1
    depends_on: [TASK-002]
    parallelizable_with: []
    files: [src\living_adr\core\graph\__init__.py]
  - id: TASK-004
    slice: 2
    story: US-2
    depends_on: [TASK-003]
    parallelizable_with: []
    files: [tests\core\test_adr_records.py]
  - id: TASK-005
    slice: 2
    story: US-2
    depends_on: [TASK-004]
    parallelizable_with: []
    files: [src\living_adr\core\adr.py]
  - id: TASK-006
    slice: 2
    story: US-6
    depends_on: [TASK-005]
    parallelizable_with: []
    files: [src\living_adr\core\adr.py]
  - id: TASK-007
    slice: 3
    story: US-3
    depends_on: [TASK-006]
    parallelizable_with: []
    files: [tests\core\graph\test_graph_ports.py]
  - id: TASK-008
    slice: 3
    story: US-3
    depends_on: [TASK-007]
    parallelizable_with: []
    files: [src\living_adr\core\graph\ports.py]
  - id: TASK-009
    slice: 3
    story: US-6
    depends_on: [TASK-008]
    parallelizable_with: []
    files: [src\living_adr\core\graph\__init__.py]
  - id: TASK-010
    slice: 4
    story: US-4
    depends_on: [TASK-009]
    parallelizable_with: []
    files: [tests\core\graph\test_approval_bound_mutation.py]
  - id: TASK-011
    slice: 4
    story: US-4
    depends_on: [TASK-010]
    parallelizable_with: []
    files: [src\living_adr\core\approval.py]
  - id: TASK-012
    slice: 4
    story: US-4
    depends_on: [TASK-011]
    parallelizable_with: []
    files: [src\living_adr\core\graph\approval_bound_mutation.py]
  - id: TASK-013
    slice: 4
    story: US-4
    depends_on: [TASK-012]
    parallelizable_with: []
    files: [tests\core\graph\test_approval_bound_mutation.py]
  - id: TASK-014
    slice: 5
    story: US-5
    depends_on: [TASK-013]
    parallelizable_with: []
    files: [tests\conformance\graph_store_conformance.py]
  - id: TASK-015
    slice: 5
    story: US-5
    depends_on: [TASK-014]
    parallelizable_with: []
    files: [tests\fakes\in_memory_graph_store.py]
  - id: TASK-016
    slice: 5
    story: US-5
    depends_on: [TASK-015]
    parallelizable_with: []
    files: [tests\conformance\test_in_memory_graph_conformance.py]
  - id: TASK-017
    slice: 5
    story: US-5
    depends_on: [TASK-016]
    parallelizable_with: []
    files: [tests\conformance\graph_store_conformance.py]
  - id: TASK-018
    slice: 6
    story: US-6
    depends_on: [TASK-017]
    parallelizable_with: []
    files: [tests\core\graph\test_graph_import_boundaries.py]
  - id: TASK-019
    slice: 6
    story: US-6
    depends_on: [TASK-018]
    parallelizable_with: []
    files: [src\living_adr\core\__init__.py]
  - id: TASK-020
    slice: 6
    story: verification
    depends_on: [TASK-019]
    parallelizable_with: [TASK-021]
    files: [tests\core\test_adr_records.py, tests\core\graph\test_graph_models.py, tests\core\graph\test_graph_ports.py, tests\core\graph\test_approval_bound_mutation.py, tests\conformance\test_in_memory_graph_conformance.py]
  - id: TASK-021
    slice: 6
    story: verification
    depends_on: [TASK-019]
    parallelizable_with: [TASK-020]
    files: [pyproject.toml]
  - id: TASK-022
    slice: 6
    story: verification
    depends_on: [TASK-019]
    parallelizable_with: []
    files: [src\living_adr\core\graph\ports.py, src\living_adr\core\graph\models.py, src\living_adr\core\graph\approval_bound_mutation.py]
```
