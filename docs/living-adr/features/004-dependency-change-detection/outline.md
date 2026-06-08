# Implementation Outline: dependency-change-detection

## Slice Strategy

The feature is decomposed into five vertical slices matching the requested size. Slice 1 establishes the generic contract consumed by Feature 008. Slice 2 detects path-level manifest/lockfile evidence. Slice 3 emits draft-eligible direct dependency changes. Slice 4 implements below-threshold no-ADR outcomes. Slice 5 integrates the producer seam, replay determinism, and observability metadata.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| S-001 | Structural-change contract foundation | US-2, US-5 | M | — | false | HITL | Defines first cross-feature contract consumed by Feature 008 and later graph/drafting paths. |
| S-002 | Dependency evidence recognition | US-1, US-2 | M | S-001 | false | AFK | Pure deterministic path/evidence normalization with fixture tests and no safety boundary. |
| S-003 | Draft-eligible direct dependency classification | US-1, US-2 | M | S-002 | false | HITL | Sets ADR-triggering confidence behavior and must be reviewed for ADR-fatigue impact. |
| S-004 | Below-threshold no-ADR outcomes | US-3, US-4 | S | S-003 | false | HITL | Controls suppression semantics that prevent unwanted drafts and must be policy-reviewed. |
| S-005 | Producer integration, replay, and telemetry | US-4, US-5 | M | S-004 | false | HITL | Integrates workflow-facing producer and observability boundary with downstream orchestration. |

## Slices

### S-001: Structural-change contract foundation

**Scope:** Define stable models/results for `StructuralChange`, `ChangeEvidence`, dependency classification outcomes, and producer protocol.
**User Stories:** US-2, US-5
**Automation:** HITL
**Automation Reason:** Cross-feature contract must be reviewed because Feature 008 and Feature 005 depend on it.

**Deliverables:**
- `src\living_adr\core\structural_change.py` with generic structural-change/evidence models.
- `src\living_adr\workflow\structural_change_producer.py` with producer protocol and result shape.
- `tests\core\test_structural_change_contract.py` with serialization/stable-id tests.

**Checkpoint Criteria:**
- [ ] `StructuralChange` and `ChangeEvidence` serialize with repository scope, SCM event links, confidence, source paths, and evidence ids.
- [ ] Stable ids are deterministic from repository/event/path/package/operation inputs.
- [ ] Producer result can represent both draft-eligible changes and no-ADR-needed outcomes.

**Context Notes:**
- Key files: architecture data model, Feature 003 spec/intent, Feature 008 brief.
- Dependencies: Feature 003 contract terminology.
- Estimated complexity: Medium.

### S-002: Dependency evidence recognition

**Scope:** Recognize dependency manifests and lockfiles and normalize candidate evidence into dependency `ChangeEvidence`.
**User Stories:** US-1, US-2
**Automation:** AFK
**Automation Reason:** Pure additive rules with deterministic fixtures and no external side effects.

**Deliverables:**
- `src\living_adr\core\dependency_evidence.py` with manifest/lockfile pattern registry and evidence builder.
- `tests\core\test_dependency_evidence.py` covering known file patterns and stable source path ordering.

**Checkpoint Criteria:**
- [ ] Supported manifest and lockfile names are classified by ecosystem and evidence kind.
- [ ] Non-dependency files are ignored deterministically.
- [ ] Evidence records include source paths, provenance, parser version, immutable hash, and safe summary.

**Context Notes:**
- Key files: Feature 003 candidate evidence contract and dependency evidence module.
- Dependencies: S-001 models.
- Estimated complexity: Medium.

### S-003: Draft-eligible direct dependency classification

**Scope:** Detect direct dependency additions/removals/version-range changes from manifest evidence and emit draft-eligible `StructuralChange` when confidence threshold is met.
**User Stories:** US-1, US-2
**Automation:** HITL
**Automation Reason:** Threshold and trigger behavior directly affect ADR creation volume.

**Deliverables:**
- `src\living_adr\workflow\dependency_classifier.py` direct manifest classifier and confidence scorer.
- `tests\workflow\test_dependency_classifier.py` with add/remove/version fixtures.

**Checkpoint Criteria:**
- [ ] Manifest-backed direct dependency additions/removals produce `adr_recommendation="draft"` when confidence >= threshold.
- [ ] Manifest+lockfile pairs deduplicate into one structural change with both source paths.
- [ ] Unsupported or ambiguous operations do not produce draft-eligible changes.

**Context Notes:**
- Key files: dependency classifier, fixtures, structural-change contract tests.
- Dependencies: S-001, S-002.
- Estimated complexity: Medium.

### S-004: Below-threshold no-ADR outcomes

**Scope:** Add explicit no-ADR-needed outcomes for lockfile-only/transitive-only churn, unsupported parsers, and low confidence.
**User Stories:** US-3, US-4
**Automation:** HITL
**Automation Reason:** Suppression policy is architecture-significant because it mitigates FM-03 ADR fatigue.

**Deliverables:**
- `src\living_adr\workflow\dependency_classifier.py` no-ADR reason codes and low-confidence paths.
- `tests\workflow\test_dependency_no_adr.py` for lockfile-only, unsupported, malformed, and replay-stable outcomes.

**Checkpoint Criteria:**
- [ ] Lockfile-only changes emit no-ADR-needed with confidence below threshold.
- [ ] Malformed/unsupported dependency evidence emits uncertain no-ADR-needed instead of unhandled exceptions.
- [ ] No-ADR outcomes retain source paths and evidence ids for replay/observability.

**Context Notes:**
- Key files: dependency classifier, no-ADR tests.
- Dependencies: S-003.
- Estimated complexity: Low-to-Medium.

### S-005: Producer integration, replay, and telemetry

**Scope:** Expose the dependency classifier as the first structural-change producer, enforce replay determinism, and emit metadata-only observability events.
**User Stories:** US-4, US-5
**Automation:** HITL
**Automation Reason:** Integrates workflow and trace boundaries that downstream orchestration depends on.

**Deliverables:**
- `src\living_adr\workflow\dependency_change_producer.py` producer facade for Feature 015/008 handoff.
- `src\living_adr\observability\classification_events.py` safe metadata event builder.
- `tests\workflow\test_dependency_producer.py` and `tests\observability\test_classification_events.py`.

**Checkpoint Criteria:**
- [ ] Identical inputs produce identical sorted outputs on repeated/replay calls.
- [ ] Producer returns draft-eligible changes and no-ADR-needed outcomes through one typed result.
- [ ] Observability metadata excludes raw diffs/file contents and includes class, confidence, reason code, source paths, and counts.

**Context Notes:**
- Key files: producer facade, observability helper, classifier tests.
- Dependencies: S-004.
- Estimated complexity: Medium.

## Slice Dependency Graph

```text
S-001 ──→ S-002 ──→ S-003 ──→ S-004 ──→ S-005
```

## Slice Dependency Graph (Machine-Readable)

```yaml
slices:
  - id: S-001
    name: Structural-change contract foundation
    depends_on: []
    parallelizable: false
    automation: HITL
    automation_reason: "Defines first cross-feature contract consumed by Feature 008 and later graph/drafting paths."
    checkpoint_criteria_count: 3
  - id: S-002
    name: Dependency evidence recognition
    depends_on: [S-001]
    parallelizable: false
    automation: AFK
    automation_reason: "Pure deterministic path/evidence normalization with fixture tests and no safety boundary."
    checkpoint_criteria_count: 3
  - id: S-003
    name: Draft-eligible direct dependency classification
    depends_on: [S-002]
    parallelizable: false
    automation: HITL
    automation_reason: "Sets ADR-triggering confidence behavior and must be reviewed for ADR-fatigue impact."
    checkpoint_criteria_count: 3
  - id: S-004
    name: Below-threshold no-ADR outcomes
    depends_on: [S-003]
    parallelizable: false
    automation: HITL
    automation_reason: "Controls suppression semantics that prevent unwanted drafts and must be policy-reviewed."
    checkpoint_criteria_count: 3
  - id: S-005
    name: Producer integration, replay, and telemetry
    depends_on: [S-004]
    parallelizable: false
    automation: HITL
    automation_reason: "Integrates workflow-facing producer and observability boundary with downstream orchestration."
    checkpoint_criteria_count: 3
```

## Context Management

- Maximum files open per slice: 5 implementation files plus current slice tests.
- Recommended context reset points: after S-001 contract approval; after S-003 threshold behavior; before S-005 integration.
- State that must carry across slices: contract fields, stable-id formula, confidence threshold, no-ADR reason codes, and source-path ordering.

## Verification Strategy

Run repository checks expected for the greenfield repo once scaffolded: `uv run ruff check` and `uv run pytest`. For this feature specifically, verify contract serialization, fixture-based classifier outcomes, replay determinism, no-ADR suppression, and observability redaction tests.
