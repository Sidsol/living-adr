# Implementation Plan: dependency-change-detection

## Technical Context

- Language/Framework: Python 3.12, Pydantic/domain models, FastAPI workflow-service integration later.
- Key Dependencies: Feature 003 `SCMEvent` and candidate evidence models; Feature 002 `RepositoryIdentity` and `Observability` port.
- Test Framework: pytest.
- Build System: uv + pyproject.toml; Ruff for lint/format.
- Architecture Anchors: `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#anti-patterns`.

## Project Structure

```text
src\living_adr\
├── core\
│   ├── structural_change.py              ← NEW: StructuralChange, ChangeEvidence, stable ids
│   └── dependency_evidence.py            ← NEW: manifest/lockfile recognition and evidence normalization
├── workflow\
│   ├── structural_change_producer.py     ← NEW: generic producer protocol/result
│   ├── dependency_classifier.py          ← NEW: scoring, direct dependency classification, no-ADR outcomes
│   └── dependency_change_producer.py     ← NEW: workflow-facing facade for Feature 015/008 handoff
└── observability\
    └── classification_events.py          ← NEW: metadata-only classifier telemetry helpers

tests\
├── core\
│   ├── test_structural_change_contract.py
│   └── test_dependency_evidence.py
├── workflow\
│   ├── test_dependency_classifier.py
│   ├── test_dependency_no_adr.py
│   └── test_dependency_producer.py
└── observability\
    └── test_classification_events.py
```

## Implementation Phases

### Phase S-001: Structural-change contract foundation

#### Step TASK-001: Write contract tests for structural-change models
- **File:** `tests\core\test_structural_change_contract.py`
- **Action:** Create
- **Changes:** Add RED tests for `StructuralChange`, `ChangeEvidence`, stable deterministic ids, `adr_recommendation`, source paths, evidence ids, and serialization for Feature 008.

#### Step TASK-002: Implement structural-change models
- **File:** `src\living_adr\core\structural_change.py`
- **Action:** Create
- **Changes:** Add typed models/enums for change type, operation, recommendation, evidence kind, no-ADR reason code, stable id/hash helpers, and validation for confidence/source paths.

#### Step TASK-003: Define generic producer result protocol
- **File:** `src\living_adr\workflow\structural_change_producer.py`
- **Action:** Create
- **Changes:** Add `StructuralChangeProducer` protocol and `StructuralChangeProducerResult` containing `changes`, `no_adr_outcomes`, `evidence`, and diagnostics.

### Phase S-002: Dependency evidence recognition

#### Step TASK-004: Write dependency evidence recognition tests
- **File:** `tests\core\test_dependency_evidence.py`
- **Action:** Create
- **Changes:** Add RED tests for manifest/lockfile patterns, ecosystem mapping, non-dependency file filtering, source path ordering, immutable evidence hash, and safe summaries.

#### Step TASK-005: Implement dependency evidence matcher and builder
- **File:** `src\living_adr\core\dependency_evidence.py`
- **Action:** Create
- **Changes:** Add registry for manifests/lockfiles, ecosystem detection, path normalization, evidence construction from Feature 003 candidate evidence, and parser version metadata.

### Phase S-003: Draft-eligible direct dependency classification

#### Step TASK-006: Write direct dependency classifier tests
- **File:** `tests\workflow\test_dependency_classifier.py`
- **Action:** Create
- **Changes:** Add RED fixtures for npm and Python direct dependency add/remove/version changes, manifest+lockfile dedupe, confidence threshold, and affected package extraction.

#### Step TASK-007: Implement direct dependency classifier and confidence scorer
- **File:** `src\living_adr\workflow\dependency_classifier.py`
- **Action:** Create
- **Changes:** Add deterministic classifier using dependency evidence, direct manifest operation extraction from before/after or diff summaries, confidence scoring, stable output ordering, and draft-eligible `StructuralChange` creation.

### Phase S-004: Below-threshold no-ADR outcomes

#### Step TASK-008: Write no-ADR behavior tests
- **File:** `tests\workflow\test_dependency_no_adr.py`
- **Action:** Create
- **Changes:** Add RED tests for lockfile-only churn, unsupported ecosystem, malformed evidence, empty/no matching files, below-threshold confidence, and stable reason codes.

#### Step TASK-009: Implement no-ADR-needed outcomes
- **File:** `src\living_adr\workflow\dependency_classifier.py`
- **Action:** Modify
- **Changes:** Add no-ADR outcome creation, reason codes, low-confidence handling, malformed evidence catch paths, and tests ensuring no draft-eligible changes leak from suppressed cases.

### Phase S-005: Producer integration, replay, and telemetry

#### Step TASK-010: Write producer integration/replay tests
- **File:** `tests\workflow\test_dependency_producer.py`
- **Action:** Create
- **Changes:** Add RED tests that the workflow-facing producer consumes fake `SCMEvent` + candidate evidence, returns typed results, and produces identical serialized output across repeated calls.

#### Step TASK-011: Implement dependency change producer facade
- **File:** `src\living_adr\workflow\dependency_change_producer.py`
- **Action:** Create
- **Changes:** Add facade implementing `StructuralChangeProducer`, invoking evidence builder/classifier, preserving no-ADR outcomes, sorting outputs, and exposing Feature 008-ready result.

#### Step TASK-012: Write telemetry redaction tests
- **File:** `tests\observability\test_classification_events.py`
- **Action:** Create
- **Changes:** Add RED tests that telemetry includes repository key, normalized PR key, counts, confidence buckets, reason codes, and source paths but excludes raw diff/file contents.

#### Step TASK-013: Implement metadata-only classification events
- **File:** `src\living_adr\observability\classification_events.py`
- **Action:** Create
- **Changes:** Add safe metadata builder for classifier started/completed/no-ADR/error events and integration hook points for the inherited `Observability` port.

#### Step TASK-014: Wire telemetry into producer facade
- **File:** `src\living_adr\workflow\dependency_change_producer.py`
- **Action:** Modify
- **Changes:** Call metadata builder/observability at start and completion, ensure errors are converted to typed uncertain outcomes where possible, and keep raw evidence out of traces.

## Complexity Tracking

| Phase | Files Changed | New Files | Estimated Effort | Risk |
|---|---:|---:|---|---|
| S-001 | 3 | 3 | M | Medium |
| S-002 | 2 | 2 | M | Low |
| S-003 | 2 | 2 | M | Medium |
| S-004 | 2 | 1 | S | Medium |
| S-005 | 5 | 4 | M | Medium |

## Dependencies & Prerequisites

- Feature 003 model names may need import-path adjustment during implementation.
- Feature 002 `RepositoryIdentity` and `Observability` port should exist before final integration; tests can use local fakes until then.
- Default draft threshold planned as `0.70`; keep configurable in code to resolve architecture open question later.
- No database migration is required unless Feature 015/006 chooses durable tables for outcomes; this feature can initially return typed records to the workflow.

## Rollback Strategy

- S-001 rollback: remove new core/protocol files and contract tests; no runtime side effects.
- S-002 rollback: remove dependency evidence module/tests; S-001 contract remains reusable.
- S-003 rollback: remove classifier implementation/tests; no draft-eligible producer remains.
- S-004 rollback: revert `dependency_classifier.py` no-ADR changes and no-ADR tests; reassess FM-03 before proceeding.
- S-005 rollback: remove producer facade/telemetry helpers and tests; classifier can remain isolated until workflow integration is redesigned.

## Machine-Readable Task Graph

```yaml
task_graph:
  - id: TASK-001
    slice: S-001
    story: US-2
    depends_on: []
    parallelizable_with: []
    files: [tests/core/test_structural_change_contract.py]
  - id: TASK-002
    slice: S-001
    story: US-2
    depends_on: [TASK-001]
    parallelizable_with: []
    files: [src/living_adr/core/structural_change.py]
  - id: TASK-003
    slice: S-001
    story: US-5
    depends_on: [TASK-002]
    parallelizable_with: []
    files: [src/living_adr/workflow/structural_change_producer.py]
  - id: TASK-004
    slice: S-002
    story: US-1
    depends_on: [TASK-003]
    parallelizable_with: []
    files: [tests/core/test_dependency_evidence.py]
  - id: TASK-005
    slice: S-002
    story: US-2
    depends_on: [TASK-004]
    parallelizable_with: []
    files: [src/living_adr/core/dependency_evidence.py]
  - id: TASK-006
    slice: S-003
    story: US-1
    depends_on: [TASK-005]
    parallelizable_with: []
    files: [tests/workflow/test_dependency_classifier.py]
  - id: TASK-007
    slice: S-003
    story: US-1
    depends_on: [TASK-006]
    parallelizable_with: []
    files: [src/living_adr/workflow/dependency_classifier.py]
  - id: TASK-008
    slice: S-004
    story: US-3
    depends_on: [TASK-007]
    parallelizable_with: []
    files: [tests/workflow/test_dependency_no_adr.py]
  - id: TASK-009
    slice: S-004
    story: US-3
    depends_on: [TASK-008]
    parallelizable_with: []
    files: [src/living_adr/workflow/dependency_classifier.py]
  - id: TASK-010
    slice: S-005
    story: US-4
    depends_on: [TASK-009]
    parallelizable_with: []
    files: [tests/workflow/test_dependency_producer.py]
  - id: TASK-011
    slice: S-005
    story: US-5
    depends_on: [TASK-010]
    parallelizable_with: []
    files: [src/living_adr/workflow/dependency_change_producer.py]
  - id: TASK-012
    slice: S-005
    story: US-4
    depends_on: [TASK-011]
    parallelizable_with: []
    files: [tests/observability/test_classification_events.py]
  - id: TASK-013
    slice: S-005
    story: US-4
    depends_on: [TASK-012]
    parallelizable_with: []
    files: [src/living_adr/observability/classification_events.py]
  - id: TASK-014
    slice: S-005
    story: US-5
    depends_on: [TASK-013]
    parallelizable_with: []
    files: [src/living_adr/workflow/dependency_change_producer.py]
```
