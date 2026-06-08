# Implementation Outline: schema-api-contract-change-detection

## Slice Strategy

The feature is decomposed into seven vertical slices: first stabilize the shared contract, then add evidence input mapping, schema detection, API detection, confidence/uncertainty policy, workflow-facing integration, and final fixture/observability verification. Schema and API behavior are intentionally separate slices so their semantics do not collapse into a generic structural-change detector.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| 1 | Shared StructuralChange contract | US-3 | M | — | false | HITL | Cross-feature contract must align with 004 and 008. |
| 2 | Evidence input adapter | US-6 | S | 1 | false | AFK | Pure adapter over feature 003 evidence fixtures once contract exists. |
| 3 | Schema change detector | US-1, US-4 | M | 2 | true | HITL | Detector semantics require human review to avoid schema/API conflation and false certainty. |
| 4 | API contract detector | US-2, US-4 | M | 2 | true | HITL | Public contract semantics and compatibility signals need review. |
| 5 | Confidence threshold and uncertainty policy | US-4, US-5 | M | 3, 4 | false | HITL | Encodes resolved configurable default threshold `0.70` and uncertainty taxonomy. |
| 6 | Classifier service integration | US-3, US-6 | M | 5 | false | HITL | Workflow-facing producer boundary affects feature 015 and 008. |
| 7 | Fixture matrix and metadata verification | US-1, US-2, US-4, US-6 | S | 6 | false | AFK | Additive tests and observability assertions after behavior is defined. |

## Slices

### Slice 1: Shared StructuralChange contract

**Scope:** Create or adopt the common `StructuralChange` / `ChangeEvidence` model used by dependency, schema, and API producers.
**User Stories:** US-3
**Automation:** HITL
**Automation Reason:** Cross-feature contract must be reviewed for compatibility with feature 004 and feature 008.

**Deliverables:**

- `src\living_adr\core\structural_change.py` with producer-neutral models and validation.
- `tests\workflow\classifiers\test_structural_change_contract.py` covering dependency/schema/API examples.

**Checkpoint Criteria:**

- [ ] Contract includes feature 004 fields for repository scope, source event ids, `change_type`, source paths, evidence ids, confidence, reason code, classifier metadata, and routing outcome.
- [ ] Schema/API examples and a dependency-shaped example use the same type without producer-specific common fields.
- [ ] Confidence bounds and evidence presence validation fail deterministically.

**Context Notes:**

- Key files: `src\living_adr\core\structural_change.py`, feature 003 event/evidence models when implemented.
- Dependencies: Feature 003 `SCMEvent`; feature 004 alignment if available.
- Estimated complexity: Medium.

### Slice 2: Evidence input adapter

**Scope:** Convert feature 003 candidate evidence into classifier-friendly immutable inputs without coupling detectors to ingestion internals.
**User Stories:** US-6
**Automation:** AFK
**Automation Reason:** Pure mapping and validation over fixture data.

**Deliverables:**

- `src\living_adr\workflow\classifiers\inputs.py` with `ClassifierInput`, changed-file summaries, and evidence references.
- Tests for missing repository scope, empty evidence, and path normalization.

**Checkpoint Criteria:**

- [ ] Adapter accepts normalized `SCMEvent` and evidence bundle, not raw GitHub payloads.
- [ ] File paths, statuses, diff refs, and summaries are preserved without raw diff export.
- [ ] Invalid or cross-repository evidence is rejected.

**Context Notes:**

- Key files: `workflow\classifiers\inputs.py`, feature 003 evidence contracts.
- Dependencies: Slice 1.
- Estimated complexity: Low.

### Slice 3: Schema change detector

**Scope:** Detect database/schema signals and emit schema-specific `StructuralChange` records with evidence and uncertainty.
**User Stories:** US-1, US-4
**Automation:** HITL
**Automation Reason:** Requires judgment on schema semantics and ambiguous/generated patterns.

**Deliverables:**

- `src\living_adr\workflow\classifiers\schema.py`.
- `tests\workflow\classifiers\test_schema_change_detection.py` with migrations, ORM fields, DDL, generated, and no-change fixtures.

**Checkpoint Criteria:**

- [ ] Migration/DDL/ORM/schema-registry evidence produces `change_type=schema` using the feature 004 serialized field set.
- [ ] Seed/test/comment-only changes do not produce high-confidence schema changes.
- [ ] Generated/runtime-limited evidence includes uncertainty notes.

**Context Notes:**

- Key files: `schema.py`, schema fixture builders.
- Dependencies: Slices 1-2.
- Estimated complexity: Medium.

### Slice 4: API contract detector

**Scope:** Detect API contract signals and emit API-specific `StructuralChange` records with evidence and uncertainty.
**User Stories:** US-2, US-4
**Automation:** HITL
**Automation Reason:** Public contract boundaries and dynamic framework routes need careful review.

**Deliverables:**

- `src\living_adr\workflow\classifiers\api_contract.py`.
- `tests\workflow\classifiers\test_api_contract_detection.py` with OpenAPI, GraphQL, protobuf/RPC, route/model/status fixtures.

**Checkpoint Criteria:**

- [ ] OpenAPI/GraphQL/protobuf/RPC/request-response signals produce `change_type=api_contract` using the feature 004 serialized field set.
- [ ] Implementation-only handler changes are not high-confidence contract changes.
- [ ] Dynamic/generated API evidence includes uncertainty notes.

**Context Notes:**

- Key files: `api_contract.py`, API fixture builders.
- Dependencies: Slices 1-2.
- Estimated complexity: Medium.

### Slice 5: Confidence threshold and uncertainty policy

**Scope:** Centralize confidence scoring, uncertainty taxonomy, threshold policy versioning, and no-ADR-needed routing.
**User Stories:** US-4, US-5
**Automation:** HITL
**Automation Reason:** The confidence threshold is resolved as configurable `semantic-change-default-v1` default `0.70`.

**Deliverables:**

- `src\living_adr\workflow\classifiers\confidence.py`.
- Tests for scoring factors, policy versions, threshold routing, and uncertainty requirements.

**Checkpoint Criteria:**

- [ ] Scoring is explainable and bounded.
- [ ] Threshold policy is configurable/versioned with default `0.70`; no magic constants in detectors.
- [ ] Low-confidence outcomes remain inspectable.
- [ ] Manifest/checklist record the resolved threshold decision and per-repository override support.

**Context Notes:**

- Key files: `confidence.py`, spec Resolved Decisions.
- Dependencies: Slices 3-4.
- Estimated complexity: Medium.

### Slice 6: Classifier service integration

**Scope:** Provide one workflow-facing service that runs schema and API detectors, de-duplicates mixed signals, emits common structural changes, and records metadata-only observability.
**User Stories:** US-3, US-6
**Automation:** HITL
**Automation Reason:** Establishes downstream boundary for workflow orchestration and ADR drafting.

**Deliverables:**

- `src\living_adr\workflow\classifiers\service.py`.
- Integration tests with mixed schema/API PR evidence and no-ADR outcomes.

**Checkpoint Criteria:**

- [ ] Service returns zero or more common `StructuralChange` records for one `SCMEvent`.
- [ ] Schema and API changes in the same PR remain distinct unless de-duplication is justified by provenance.
- [ ] Observability emits counts/classes/policy ids only.

**Context Notes:**

- Key files: `service.py`, `inputs.py`, detectors, observability port.
- Dependencies: Slice 5.
- Estimated complexity: Medium.

### Slice 7: Fixture matrix and metadata verification

**Scope:** Complete regression fixtures, quality checks, and documentation notes for high-ambiguity classifier behavior.
**User Stories:** US-1, US-2, US-4, US-6
**Automation:** AFK
**Automation Reason:** Final additive verification once behavior and policies are stable.

**Deliverables:**

- `tests\fixtures\classifier_evidence\...` or Python fixture builders.
- Metadata leakage tests and docs/comments for threshold decision.

**Checkpoint Criteria:**

- [ ] Fixture matrix covers direct, ambiguous, generated, mixed, and no-change cases.
- [ ] No raw diffs or secrets are passed into observability metadata.
- [ ] `uv run pytest` and `uv run ruff check` pass.

**Context Notes:**

- Key files: tests under `tests\workflow\classifiers`.
- Dependencies: Slice 6.
- Estimated complexity: Low.

## Slice Dependency Graph

```text
Slice 1 ──→ Slice 2 ──→ Slice 3 ──┐
                    └──→ Slice 4 ──┴──→ Slice 5 ──→ Slice 6 ──→ Slice 7
```

## Slice Dependency Graph (Machine-Readable)

```yaml
slices:
  - id: 1
    name: Shared StructuralChange contract
    depends_on: []
    parallelizable: false
    automation: HITL
    automation_reason: "Cross-feature contract must align with 004 and 008."
    checkpoint_criteria_count: 3
  - id: 2
    name: Evidence input adapter
    depends_on: [1]
    parallelizable: false
    automation: AFK
    automation_reason: "Pure adapter over feature 003 evidence fixtures once contract exists."
    checkpoint_criteria_count: 3
  - id: 3
    name: Schema change detector
    depends_on: [2]
    parallelizable: true
    automation: HITL
    automation_reason: "Detector semantics require human review to avoid schema/API conflation and false certainty."
    checkpoint_criteria_count: 3
  - id: 4
    name: API contract detector
    depends_on: [2]
    parallelizable: true
    automation: HITL
    automation_reason: "Public contract semantics and compatibility signals need review."
    checkpoint_criteria_count: 3
  - id: 5
    name: Confidence threshold and uncertainty policy
    depends_on: [3, 4]
    parallelizable: false
    automation: HITL
    automation_reason: "Encodes resolved configurable default threshold `0.70` and uncertainty taxonomy."
    checkpoint_criteria_count: 4
  - id: 6
    name: Classifier service integration
    depends_on: [5]
    parallelizable: false
    automation: HITL
    automation_reason: "Workflow-facing producer boundary affects feature 015 and 008."
    checkpoint_criteria_count: 3
  - id: 7
    name: Fixture matrix and metadata verification
    depends_on: [6]
    parallelizable: false
    automation: AFK
    automation_reason: "Additive tests and observability assertions after behavior is defined."
    checkpoint_criteria_count: 3
```

## Context Management

- Maximum files open per slice: 6.
- Recommended context window reset points: after Slice 2, after Slice 5, before Slice 7 final verification.
- State that must carry across slices: common `StructuralChange` shape, threshold policy name/version, uncertainty taxonomy, feature 003 evidence assumptions.

## Verification Strategy

Run targeted classifier tests after each slice, then full repository verification with `uv run pytest` and `uv run ruff check`. Planning readiness is unblocked because the confidence threshold is resolved as configurable default `0.70`; implementation still verifies with `uv run pytest` and `uv run ruff check`.
