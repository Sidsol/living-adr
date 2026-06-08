# Architecture Intent: dependency-change-detection

## Current State

LivingADR is greenfield with architecture-level contracts but no production classifier code. Feature 003 will provide the normalized `SCMEvent`, `SCMProvider` fetch handles, and immutable candidate evidence stream. The project architecture already defines `StructuralChange` and `ChangeEvidence` as repository-scoped data model concepts and graph-port types, but detailed fields and the first producer are left to feature-level planning (`..\..\architecture.md#data-model`, `..\..\architecture.md#service-boundaries`).

The architecture also requires source-of-truth discipline: code and PR data are evidence; approved ADRs are authoritative rationale; graph nodes are projections with citations (`..\..\architecture.md#cross-cutting`). Anti-patterns FM-03 and FM-06 require avoiding ADR fatigue and hallucinated rationale (`..\..\architecture.md#anti-patterns`).

## Desired State

After this feature, `living-adr` has a deterministic dependency structural-change producer that consumes only Feature 003 evidence, identifies manifest-backed direct dependency changes, emits immutable `ChangeEvidence`, emits draft-eligible dependency `StructuralChange` records when confidence meets threshold, and records no-ADR-needed outcomes otherwise. Feature 008 can consume those records without live SCM calls or raw GitHub payloads.

## StructuralChange Contract Produced for Feature 008

```python
class StructuralChange:
    id: str                              # stable deterministic id
    repository: RepositoryIdentity
    source_scm_event_id: str
    provider_delivery_id: str
    normalized_pr_key: str
    change_type: Literal["dependency"]
    operation: Literal["added", "removed", "version_changed", "mixed"]
    affected_dependency: str | None
    dependency_ecosystem: str | None     # python, npm, go, rust, jvm, ruby, dotnet, unknown
    source_paths: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: float                    # 0.0..1.0
    reason_code: str                     # e.g. direct_manifest_add, manifest_lockfile_pair
    adr_recommendation: Literal["draft", "no_adr_needed"]
    classifier_name: Literal["dependency-change"]
    classifier_version: str
```

## ChangeEvidence Contract Produced for Feature 008

```python
class ChangeEvidence:
    id: str                              # stable deterministic id
    repository: RepositoryIdentity
    source_scm_event_id: str
    provider_delivery_id: str
    normalized_pr_key: str
    evidence_kind: Literal["dependency_manifest", "dependency_lockfile", "dependency_diff_summary"]
    source_path: str
    diff_hunk_ref: str | None            # reference/offset only; no raw diff export required
    before_value: str | None             # package/version/range summary when available
    after_value: str | None
    observed_operation: Literal["added", "removed", "version_changed", "lockfile_churn", "unknown"]
    parser: str
    parser_version: str
    immutable_hash: str
    summary: str                         # redaction-safe evidence summary
    provenance: dict[str, str]           # event/evidence source references only
```

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Classifier invocation | Feature 003 emits candidate evidence; no classifier exists | `DependencyChangeProducer` consumes evidence and returns typed results | Add workflow-facing producer module and fakeable interface |
| Manifest recognition | Architecture names dependency structural changes only conceptually | Filename/path matcher for manifests and lockfiles | Add deterministic path rules and tests |
| Evidence normalization | Feature 003 candidate evidence is generic | Dependency-specific immutable `ChangeEvidence` records | Add evidence builder that preserves source paths/provenance |
| Confidence threshold | Architecture open question asks what threshold distinguishes no-ADR | Tested default threshold with configurable constant | Add scoring model and no-ADR result semantics |
| `StructuralChange` fields | Architecture says detailed fields belong to feature plans | Dependency `StructuralChange` contract sufficient for Feature 008 | Define fields and serialization tests |
| Below-threshold path | FM-03 warns against fatigue | Explicit no-ADR-needed outcomes and no draft handoff | Add typed outcome and tests |
| Observability | Metadata-only discipline exists | Classifier telemetry with no raw diffs | Add instrumentation points and redaction tests |
| Extensibility | Feature 005 will add schema/API producers | Generic structural-change interfaces not polluted by dependency details | Keep dependency extras in optional/typed fields |

## Architecture Options

### Option A: Direct file-name heuristic only

**Approach:** If any dependency-like file path changes, emit a draft-eligible `StructuralChange` with a fixed confidence.

- ✅ Pros: Very small; easy to implement quickly; works with minimal Feature 003 evidence.
- ❌ Cons: Too noisy; lockfile churn causes ADR fatigue; fails FM-03; weak evidence for Feature 008.
- 🔧 Effort: Low.

### Option B: Deterministic manifest-first classifier with no-ADR outcomes (selected)

**Approach:** Recognize manifests/lockfiles, parse or inspect candidate evidence for direct dependency operations, score confidence, emit immutable evidence, draft only above threshold, and record explicit no-ADR outcomes for weak signals.

- ✅ Pros: Aligns with `..\..\architecture.md#data-model`; deterministic/testable; avoids GitHub leakage; supports Feature 008 immediately; mitigates FM-03/FM-06.
- ❌ Cons: Requires more typed contracts and fixtures; initial ecosystem parsing is intentionally shallow.
- 🔧 Effort: Medium.

### Option C: LLM-assisted dependency intent classifier

**Approach:** Send PR/diff evidence to Claude to classify dependency intent and ADR worthiness.

- ✅ Pros: Can interpret ambiguous cases and PR descriptions; may infer rationale-like context.
- ❌ Cons: Violates this feature's deterministic/testable requirement; increases prompt-injection/data-egress surface; duplicates Feature 008; risks FM-06 hallucinated rationale.
- 🔧 Effort: Medium-to-High.

## Selected Approach

**Option B: Deterministic manifest-first classifier with no-ADR outcomes.**

Rationale: This approach is the smallest contract-stable producer that unblocks Feature 008 while respecting architecture anchors. It keeps `workflow-service` and `core` boundaries clean (`..\..\architecture.md#service-boundaries`), fills in `StructuralChange`/`ChangeEvidence` detail (`..\..\architecture.md#data-model`), preserves metadata-only and source-of-truth discipline (`..\..\architecture.md#cross-cutting`), and directly mitigates FM-03 and FM-06 (`..\..\architecture.md#anti-patterns`).

## Module Surface Analysis

| Module | Inputs | Callers | Deletion test | Isolated-test candidate |
|---|---:|---|---|---|
| `src\living_adr\core\structural_change.py` | repository, SCM event ids, evidence ids, confidence | classifiers, Feature 008, graph ports | Deleting removes generic producer/consumer contract | Yes — pure models/serialization |
| `src\living_adr\core\dependency_evidence.py` | candidate evidence, file paths, diff summaries | dependency classifier | Deleting removes dependency-specific evidence normalization | Yes — pure functions with fixtures |
| `src\living_adr\workflow\dependency_classifier.py` | `SCMEvent`, candidate evidence, threshold | Feature 015 workflow node, tests | Deleting removes first structural-change producer | Yes — fake evidence/no IO |
| `src\living_adr\workflow\structural_change_producer.py` | typed classifier results | workflow orchestration | Deleting forces classifier-specific workflow coupling | Yes — protocol/result tests |
| `src\living_adr\observability\classification_events.py` | classification metadata | classifier/workflow | Deleting risks trace inconsistency/leakage | Yes — metadata builder tests |
| `tests\workflow\test_dependency_classifier.py` | fixtures for manifests/lockfiles | pytest | Deleting risks false positives/negatives | n/a |
| `tests\core\test_structural_change_contract.py` | model fixtures | pytest | Deleting risks Feature 008 contract drift | n/a |

## Anti-Patterns to Avoid

- **Lockfile change equals ADR:** tempting but noisy; lockfile-only churn should usually become no-ADR-needed.
- **Raw GitHub payload dependency:** violates Feature 003 boundary and FM-24; consume normalized evidence only.
- **LLM classification in this feature:** undermines replay determinism and increases FM-06 risk.
- **Evidence as rationale:** `ChangeEvidence` proves what changed; it does not explain why without HITL-approved ADRs.
- **Silent suppression:** below-threshold outcomes must be persisted/observable, not dropped.
- **Broad repository mining:** violates FM-18; use merged-PR evidence only.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add core structural-change/evidence contracts, dependency classifier workflow module, metadata-only observability helpers, and pytest fixtures | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Feature 003 evidence shape changes during implementation | Medium | Medium | Depend on typed candidate evidence protocol and write adapter tests. |
| Lockfile parser complexity exceeds slice size | Medium | Medium | Treat lockfiles primarily as supporting evidence; direct manifest parsing drives threshold. |
| False positives create ADR fatigue | Medium | High | Require manifest-backed signal for draft threshold; record no-ADR outcomes. |
| False negatives miss meaningful dependency decisions | Medium | Medium | Preserve below-threshold evidence/reason codes for replay and later rule tuning. |
| Contract too dependency-specific for Feature 005 | Low | High | Keep generic `StructuralChange` fields plus optional dependency fields; document producer interface. |
| Observability leaks raw dependency content | Low | High | Centralize metadata builder and test it excludes raw diff/file contents. |
