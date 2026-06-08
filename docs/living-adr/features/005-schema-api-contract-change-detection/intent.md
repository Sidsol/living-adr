# Architecture Intent: schema-api-contract-change-detection

## Current State

LivingADR is scaffold-only in `C:\repos\living-adr`; no schema/API classifiers, workflow nodes, evidence models, or `StructuralChange` code exist yet. Feature 003 defines the upstream intent for `SCMEvent`, `SCMProvider`, and candidate evidence from merged PRs. The architecture already assigns structural-change classification to TH-02 and defines `StructuralChange` / `ChangeEvidence` as repository-scoped data model concepts (`..\..\architecture.md#data-model`).

Feature 004's `spec.md` and `intent.md` were read during this update. They define the first producer contract for feature 008. Feature 005 must reuse `core\structural_change.py` and must not introduce a parallel schema/API contract; it must reuse feature 004's `StructuralChange` and `ChangeEvidence` serialized field set byte-identically. Schema/API-specific semantics are represented through existing shared fields (`change_type`, `operation`, `reason_code`, `classifier_name`, `source_paths`, `evidence_ids`, `confidence`, `adr_recommendation`, and evidence summaries/provenance).

Relevant anchors:

- `..\..\architecture.md#service-boundaries`: workflow-service owns LangGraph workflow; core owns domain types and ports; SCM evidence comes through provider seams.
- `..\..\architecture.md#data-model`: `SCMEvent`, `StructuralChange`, and `ChangeEvidence` are repository-scoped and evidence is separate from inferred rationale.
- `..\..\architecture.md#cross-cutting`: raw diffs/prompts are default-deny for observability; source-of-truth discipline treats code/PR data as evidence.
- `..\..\architecture.md#anti-patterns`: FM-03, FM-06, FM-07, FM-18, FM-19, FM-21 warn about ADR fatigue, hallucinated rationale, static blind spots, broad fetching, PR summary overtrust, and trace leakage.

## Desired State

After this feature, workflow code can invoke a deterministic schema/API classifier on a feature-003 evidence bundle and receive zero or more feature-004-compatible `StructuralChange` records. Schema and API contract semantics remain distinct, each record cites `ChangeEvidence`, confidence is explainable, and uncertainty is explicit whenever static PR evidence cannot prove runtime or generated behavior.

The output is non-authoritative. It can trigger ADR drafting and review, but it cannot mutate graph state or become rationale until downstream HITL approval.

## Shared StructuralChange Contract

Feature 005 must consume/reuse the exact field set produced by feature 004. The following definitions are copied from `..\004-dependency-change-detection\intent.md`; implementation tests for feature 005 must assert byte-identical serialized keys/order against this contract.

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

Feature 005 implementation constraint:

- Do not add/remove/rename serialized fields relative to feature 004.
- If code-level type hints need to accept schema/API values, widen the allowed enum values in the shared feature-004 module without changing the serialized field set. For feature 005, expected semantic values are `change_type in {"schema", "api_contract"}`, `classifier_name="schema-api-contract-change-detection"`, and reason codes such as `schema_migration`, `schema_generated_uncertain`, `api_openapi_contract`, or `api_dynamic_route_uncertain`.
- Keep dependency-specific field names present for byte-identical shape. When they do not apply, set `affected_dependency=None` and `dependency_ecosystem=None`.
- Use `adr_recommendation="draft"` when confidence is at or above the active threshold; use `adr_recommendation="no_adr_needed"` below threshold while still retaining `ChangeEvidence`.
- Record uncertainty/threshold metadata in `reason_code`, redaction-safe `summary`, and `provenance` without introducing new top-level fields.

## Confidence Threshold Decision

OQ-005-1 is resolved: use configurable policy `semantic-change-default-v1` with default threshold `0.70`. Repository-level overrides are allowed. Candidates below threshold are emitted as low-confidence evidence/no-ADR-needed outcomes and are not dropped. Feature 009 HITL review remains the authoritative filter for all draft-eligible outputs.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Shared change models | Feature 004 defines first `StructuralChange` / `ChangeEvidence` field set | Feature 005 emits byte-identical serialized fields with schema/API semantic values | Reuse `core\structural_change.py`; add compatibility tests, not a parallel contract |
| Evidence input | Feature 003 planned candidate evidence | Classifier reads normalized evidence only | Define adapter from feature 003 bundle to classifier input |
| Schema detection | None | Detect migrations, DDL, ORM/persistence model, schema registry, validation schemas | Add schema detector and fixtures |
| API detection | None | Detect OpenAPI/GraphQL/protobuf/RPC/routes/request/response/status changes | Add API detector and fixtures |
| Confidence | Feature 004 assumes `0.70`; user resolved OQ-005-1 | Configurable `semantic-change-default-v1` default threshold `0.70` with per-repo override | Add scoring/policy module and tests for below-threshold retention |
| Uncertainty | Architecture warns about static blind spots | Explicit notes for generated/runtime/dynamic ambiguity | Add uncertainty taxonomy and assertions |
| Workflow integration | No classifier node | Pure classifier service callable from feature 015 | Add service facade and no side effects |
| Observability | No classifier metrics | Metadata-only counts, no raw diff export | Instrument through inherited port |

## Architecture Options

### Option A: Single broad structural-change LLM classifier

**Approach:** Send PR evidence to Claude and ask it to classify schema/API/dependency changes in one prompt.

- ✅ Pros: Fast to prototype; captures nuanced language in PR descriptions.
- ❌ Cons: Violates deterministic classifier expectation; increases data egress; risks FM-06 hallucinated rationale and FM-19 PR summary overtrust; hard to test threshold semantics.
- 🔧 Effort: Low initially, high to harden.

### Option B: Deterministic heuristic detectors with shared output contract (selected)

**Approach:** Implement pure detectors over file paths, changed-file metadata, and diff summaries/handles from feature 003. Use rule families for schema and API evidence, score confidence from explainable factors, and emit feature-004-compatible `StructuralChange` records.

- ✅ Pros: Deterministic and testable without live services; honors minimal evidence fetch; separates schema/API semantics; keeps Claude for downstream drafting; makes uncertainty explicit.
- ❌ Cons: Initial coverage may miss framework-specific dynamic changes; requires careful fixture design and later tuning.
- 🔧 Effort: Medium.

### Option C: Static analysis/generator execution per framework

**Approach:** Invoke framework-specific tools, OpenAPI generators, database migration analyzers, or code parsers to compute precise contract/schema deltas.

- ✅ Pros: Potentially higher precision for supported stacks.
- ❌ Cons: Overfits unknown PoC repository stack; introduces tool execution risk, dependency bloat, runtime side effects, and slow PR-to-draft latency.
- 🔧 Effort: High.

## Selected Approach

**Option B: Deterministic heuristic detectors with shared output contract.**

Rationale: The architecture prioritizes minimal merged-PR evidence, deterministic workflow seams, human review, and explicit uncertainty. Option B is the smallest approach that covers both MVP trigger classes without letting runtime/generated blind spots masquerade as certainty. It also keeps feature 008's Claude drafting focused on explanation from cited evidence rather than first-line structural detection.

## Module Surface Analysis

| Module | Inputs | Callers | Deletion test | Isolated-test candidate |
|---|---:|---|---|---|
| `src\living_adr\core\structural_change.py` | repository, `SCMEvent`, evidence fields | feature 004/005/008/015 | Deleting forces each producer to invent incompatible change shapes | Yes — pure validation |
| `src\living_adr\workflow\classifiers\inputs.py` | feature 003 evidence bundle | classifier service | Deleting couples detectors to ingestion internals | Yes — fake evidence fixtures |
| `src\living_adr\workflow\classifiers\schema.py` | classifier input, path/diff summaries | classifier service | Deleting loses schema trigger class | Yes — pure fixtures |
| `src\living_adr\workflow\classifiers\api_contract.py` | classifier input, path/diff summaries | classifier service | Deleting loses API trigger class | Yes — pure fixtures |
| `src\living_adr\workflow\classifiers\confidence.py` | evidence factors, policy | schema/API detectors | Deleting hides threshold and uncertainty choices | Yes — table tests |
| `src\living_adr\workflow\classifiers\service.py` | `SCMEvent`, evidence bundle, policy, observability | LangGraph node in feature 015; tests | Deleting removes common classifier facade | Yes — fakes/no network |
| `tests\workflow\classifiers\test_schema_change_detection.py` | fixture inputs | pytest | Deleting risks schema regression | n/a |
| `tests\workflow\classifiers\test_api_contract_detection.py` | fixture inputs | pytest | Deleting risks API regression | n/a |
| `tests\workflow\classifiers\test_structural_change_contract.py` | model fixtures | pytest | Deleting risks 004/008 incompatibility | n/a |
| `tests\workflow\classifiers\test_confidence_uncertainty.py` | scoring matrix | pytest | Deleting risks hidden threshold drift | n/a |

## Anti-Patterns to Avoid

- **Generic structural bucket:** schema and API semantics must remain distinct for downstream ADR context.
- **Schema/API conflation from generated files:** generated OpenAPI or migration files can be evidence, but do not infer causality without uncertainty.
- **Magic confidence constants:** the default `0.70` threshold must live in named policy `semantic-change-default-v1`, allow per-repo override, and be test-covered.
- **Dropping low-confidence signals:** keep no-ADR-needed/low-confidence outcomes for tuning and review of false negatives.
- **Raw diff observability:** do not export raw diffs or code snippets through metadata traces.
- **Model output as classifier authority:** Claude may draft later, but this feature should not require LLM calls to decide trigger classes.
- **Broad repository mining:** stay inside feature 003 evidence; do not scan the whole repository history.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add shared change models if absent, schema/API classifier modules, confidence policy, service facade, metadata-only observability, and deterministic tests | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Feature 005 drifts from feature 004 contract | Low | High | Reuse `core\structural_change.py`; add byte-identical serialized-key tests copied from feature 004 for dependency/schema/API examples. |
| Threshold choice creates too many/no ADR candidates | Medium | Medium | Use resolved configurable default `0.70`, preserve below-threshold evidence, and rely on feature 009 HITL as authoritative filter. |
| Static diff misses runtime schema/API changes | High | Medium | Emit uncertainty taxonomy; keep confidence conservative; allow reviewer/drafting to request more context. |
| Generated artifacts cause duplicate schema and API changes | Medium | Medium | De-duplicate by subject/evidence provenance and mark generated links as uncertainty. |
| Detector overfits one framework | Medium | Medium | Use broad evidence families and fixture matrix; keep parser-free rules first. |
| Raw diffs leak into traces | Medium | High | Observability wrapper accepts only counts/classes/policy ids; tests assert no raw evidence payload fields. |
