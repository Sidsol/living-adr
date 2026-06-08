# Implementation Plan: schema-api-contract-change-detection

## Technical Context

- Language/Framework: Python 3.12, package under `src\living_adr`.
- Key Dependencies: existing project dependencies only; prefer stdlib, dataclasses/Pydantic if already used by adjacent features, pytest, Ruff.
- Test Framework: pytest.
- Build System: uv with `pyproject.toml`.
- Upstream dependency: feature 003 `SCMEvent` and candidate evidence bundle.
- Confidence threshold: OQ-005-1 is resolved as configurable policy `semantic-change-default-v1` with default threshold `0.70` and per-repository override support; below-threshold candidates are retained as low-confidence evidence/no-ADR-needed outcomes.

## Project Structure

```text
src\living_adr\
├── core\
│   └── structural_change.py               ← MODIFY/REUSE: feature 004 byte-identical StructuralChange and ChangeEvidence contract
└── workflow\
    └── classifiers\
        ├── __init__.py                    ← CREATE: package exports
        ├── inputs.py                      ← CREATE: feature 003 evidence adapter
        ├── schema.py                      ← CREATE: schema detector
        ├── api_contract.py                ← CREATE: API contract detector
        ├── confidence.py                  ← CREATE: scoring, uncertainty, threshold policy
        └── service.py                     ← CREATE: workflow-facing classifier service
tests\workflow\classifiers\
├── test_structural_change_contract.py     ← CREATE
├── test_inputs.py                         ← CREATE
├── test_schema_change_detection.py        ← CREATE
├── test_api_contract_detection.py         ← CREATE
├── test_confidence_uncertainty.py         ← CREATE
└── test_classifier_service.py             ← CREATE
```

## Implementation Phases

### Phase 1: Shared StructuralChange contract

#### Step 1.1: Write RED contract tests
- **File:** `tests\workflow\classifiers\test_structural_change_contract.py`
- **Action:** Create
- **Changes:** Add tests proving schema/API outputs serialize with the exact feature 004 `StructuralChange`/`ChangeEvidence` field set, dependency-shaped examples still pass, confidence is bounded, and low-confidence evidence is retained.

#### Step 1.2: Implement common change models
- **File:** `src\living_adr\core\structural_change.py`
- **Action:** Modify or Reuse
- **Changes:** Reuse feature 004's `StructuralChange` and `ChangeEvidence` field set byte-identically. If needed, widen allowed enum values for schema/API in the shared module without adding/removing/renaming serialized fields.

### Phase 2: Evidence input adapter

#### Step 2.1: Write RED evidence adapter tests
- **File:** `tests\workflow\classifiers\test_inputs.py`
- **Action:** Create
- **Changes:** Add fixtures for feature 003-like `SCMEvent` evidence, path normalization, cross-repository rejection, empty evidence handling, and raw diff avoidance.

#### Step 2.2: Implement classifier input adapter
- **File:** `src\living_adr\workflow\classifiers\inputs.py`
- **Action:** Create
- **Changes:** Define `ClassifierInput`, `ChangedFileEvidence`, normalized file status/path fields, summary/diff-ref references, and conversion from upstream evidence bundle.

#### Step 2.3: Create classifier package exports
- **File:** `src\living_adr\workflow\classifiers\__init__.py`
- **Action:** Create
- **Changes:** Export stable facade types only; do not expose detector internals as workflow contract.

### Phase 3: Schema change detector

#### Step 3.1: Write RED schema detector tests
- **File:** `tests\workflow\classifiers\test_schema_change_detection.py`
- **Action:** Create
- **Changes:** Add migration, SQL DDL, ORM model, schema registry, validation schema, seed/test/comment-only, generated migration, and runtime-limited fixtures.

#### Step 3.2: Implement schema detector
- **File:** `src\living_adr\workflow\classifiers\schema.py`
- **Action:** Create
- **Changes:** Add rule families for schema paths/extensions/diff summaries, schema subtypes, subject extraction, evidence creation, and uncertainty notes.

### Phase 4: API contract detector

#### Step 4.1: Write RED API detector tests
- **File:** `tests\workflow\classifiers\test_api_contract_detection.py`
- **Action:** Create
- **Changes:** Add OpenAPI, GraphQL, protobuf/RPC, route signature, request/response model, status/error semantics, internal-only handler, generated artifact, and dynamic route fixtures.

#### Step 4.2: Implement API contract detector
- **File:** `src\living_adr\workflow\classifiers\api_contract.py`
- **Action:** Create
- **Changes:** Add API evidence rule families, subtypes, subject extraction, evidence creation, and generated/dynamic uncertainty notes.

### Phase 5: Confidence threshold and uncertainty policy

#### Step 5.1: Write RED policy tests
- **File:** `tests\workflow\classifiers\test_confidence_uncertainty.py`
- **Action:** Create
- **Changes:** Cover direct evidence boosts, generated/runtime uncertainty penalties, confidence bounds, no-ADR-needed routing, policy version inclusion, default threshold `0.70`, and per-repository override behavior.

#### Step 5.2: Implement scoring and policy module
- **File:** `src\living_adr\workflow\classifiers\confidence.py`
- **Action:** Create
- **Changes:** Define `ConfidencePolicy`, `UncertaintyReason`, scoring factors, routing decision, policy version `semantic-change-default-v1`, default threshold `0.70`, and per-repository override support.

#### Step 5.3: Wire detectors to policy
- **File:** `src\living_adr\workflow\classifiers\schema.py`; `src\living_adr\workflow\classifiers\api_contract.py`
- **Action:** Modify
- **Changes:** Replace local scoring with shared policy and ensure emitted feature-004-compatible records carry threshold/uncertainty in `reason_code`, redaction-safe summaries, and `provenance`.

### Phase 6: Classifier service integration

#### Step 6.1: Write RED service tests
- **File:** `tests\workflow\classifiers\test_classifier_service.py`
- **Action:** Create
- **Changes:** Test zero/multiple outputs, mixed schema/API PRs, de-duplication by subject/provenance, low-confidence retention, and metadata-only observability.

#### Step 6.2: Implement classifier service facade
- **File:** `src\living_adr\workflow\classifiers\service.py`
- **Action:** Create
- **Changes:** Add `SchemaApiContractClassifier` or equivalent facade that accepts `SCMEvent`, evidence bundle/input, confidence policy, and observability; returns classification result with changes and no-ADR outcomes.

#### Step 6.3: Update package exports
- **File:** `src\living_adr\workflow\classifiers\__init__.py`
- **Action:** Modify
- **Changes:** Export service facade, policy type, and stable inputs for feature 015; avoid exporting raw detector rule tables.

### Phase 7: Fixture matrix and metadata verification

#### Step 7.1: Complete regression fixture matrix
- **File:** `tests\workflow\classifiers\test_schema_change_detection.py`; `tests\workflow\classifiers\test_api_contract_detection.py`; `tests\workflow\classifiers\test_classifier_service.py`
- **Action:** Modify
- **Changes:** Add direct, ambiguous, generated, mixed, and no-change cases; assert schema/API distinctness.

#### Step 7.2: Add observability leakage assertions
- **File:** `tests\workflow\classifiers\test_classifier_service.py`
- **Action:** Modify
- **Changes:** Assert emitted observability metadata contains class/count/policy/uncertainty reason only and excludes raw diff/source fields.

#### Step 7.3: Run verification
- **File:** n/a
- **Action:** Verify
- **Changes:** Run `uv run pytest` and `uv run ruff check` from `C:\repos\living-adr`.

## Complexity Tracking

| Phase | Files Changed | New Files | Estimated Effort | Risk |
|---|---:|---:|---|---|
| Phase 1 | 0-1 | 2 | M | High |
| Phase 2 | 0 | 3 | S | Low |
| Phase 3 | 0 | 2 | M | Medium |
| Phase 4 | 0 | 2 | M | Medium |
| Phase 5 | 2 | 2 | M | High |
| Phase 6 | 1 | 2 | M | Medium |
| Phase 7 | 3 | 0 | S | Low |

## Dependencies & Prerequisites

- Feature 003 implementation or stable stubs for `SCMEvent` and candidate evidence.
- Feature 004 alignment: reuse `core\structural_change.py` and keep the serialized contract byte-identical.
- Confidence threshold decision OQ-005-1 is resolved: default `0.70`, configurable per repository.
- Existing `uv`, pytest, and Ruff setup in `C:\repos\living-adr`.

## Rollback Strategy

Each phase is additive. Roll back by reverting the phase's created files and package exports. If `core\structural_change.py` is shared with feature 004, rollback must preserve the byte-identical dependency-change fields already consumed by other features. If threshold policy proves noisy, lower routing by policy configuration without deleting retained low-confidence evidence behavior.

## Machine-Readable Task Graph

```yaml
task_graph:
  - id: TASK-001
    slice: 1
    story: US-3
    depends_on: []
    parallelizable_with: []
    files: [tests\\workflow\\classifiers\\test_structural_change_contract.py]
  - id: TASK-002
    slice: 1
    story: US-3
    depends_on: [TASK-001]
    parallelizable_with: []
    files: [src\\living_adr\\core\\structural_change.py]
  - id: TASK-003
    slice: 2
    story: US-6
    depends_on: [TASK-002]
    parallelizable_with: []
    files: [tests\\workflow\\classifiers\\test_inputs.py]
  - id: TASK-004
    slice: 2
    story: US-6
    depends_on: [TASK-003]
    parallelizable_with: []
    files: [src\\living_adr\\workflow\\classifiers\\inputs.py]
  - id: TASK-005
    slice: 2
    story: US-6
    depends_on: [TASK-004]
    parallelizable_with: []
    files: [src\\living_adr\\workflow\\classifiers\\__init__.py]
  - id: TASK-006
    slice: 3
    story: US-1
    depends_on: [TASK-004]
    parallelizable_with: [TASK-008]
    files: [tests\\workflow\\classifiers\\test_schema_change_detection.py]
  - id: TASK-007
    slice: 3
    story: US-1
    depends_on: [TASK-006]
    parallelizable_with: [TASK-008]
    files: [src\\living_adr\\workflow\\classifiers\\schema.py]
  - id: TASK-008
    slice: 4
    story: US-2
    depends_on: [TASK-004]
    parallelizable_with: [TASK-006]
    files: [tests\\workflow\\classifiers\\test_api_contract_detection.py]
  - id: TASK-009
    slice: 4
    story: US-2
    depends_on: [TASK-008]
    parallelizable_with: []
    files: [src\\living_adr\\workflow\\classifiers\\api_contract.py]
  - id: TASK-010
    slice: 5
    story: US-4
    depends_on: [TASK-007, TASK-009]
    parallelizable_with: []
    files: [tests\\workflow\\classifiers\\test_confidence_uncertainty.py]
  - id: TASK-011
    slice: 5
    story: US-4
    depends_on: [TASK-010]
    parallelizable_with: []
    files: [src\\living_adr\\workflow\\classifiers\\confidence.py]
  - id: TASK-012
    slice: 5
    story: US-5
    depends_on: [TASK-011]
    parallelizable_with: []
    files: [src\\living_adr\\workflow\\classifiers\\schema.py, src\\living_adr\\workflow\\classifiers\\api_contract.py]
  - id: TASK-013
    slice: 6
    story: US-3
    depends_on: [TASK-012]
    parallelizable_with: []
    files: [tests\\workflow\\classifiers\\test_classifier_service.py]
  - id: TASK-014
    slice: 6
    story: US-6
    depends_on: [TASK-013]
    parallelizable_with: []
    files: [src\living_adr\workflow\classifiers\service.py]
  - id: TASK-015
    slice: 6
    story: US-3
    depends_on: [TASK-014]
    parallelizable_with: []
    files: [src\\living_adr\\workflow\\classifiers\\__init__.py]
  - id: TASK-016
    slice: 7
    story: US-1
    depends_on: [TASK-015]
    parallelizable_with: []
    files: [tests\\workflow\\classifiers\\test_schema_change_detection.py, tests\\workflow\\classifiers\\test_api_contract_detection.py, tests\\workflow\\classifiers\\test_classifier_service.py]
  - id: TASK-017
    slice: 7
    story: US-6
    depends_on: [TASK-016]
    parallelizable_with: []
    files: [tests\\workflow\\classifiers\\test_classifier_service.py]
  - id: TASK-018
    slice: 7
    story: US-4
    depends_on: [TASK-017]
    parallelizable_with: []
    files: []
```
