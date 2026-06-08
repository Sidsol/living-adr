# Feature Specification: schema-api-contract-change-detection

## Overview

Feature 005 detects database/schema changes and API contract changes from merged-PR evidence produced by feature 003. It emits repository-scoped `StructuralChange` classifications with immutable `ChangeEvidence`, confidence, and explicit uncertainty notes for cases where static diffs cannot prove runtime or generated behavior.

This feature is a TH-02 follow-on producer to feature 004 `dependency-change-detection`. Feature 004's `spec.md` and `intent.md` define the first `StructuralChange` / `ChangeEvidence` contract. Feature 005 must reuse that same emitted contract byte-for-byte at the serialized field level: same field names, same evidence field names, and no schema/API-specific replacement contract. Schema/API semantics are carried through the shared `change_type`, `operation`, `reason_code`, `classifier_name`, `source_paths`, evidence summaries, and confidence fields so feature 008 consumes all structural changes uniformly.

## Canonical Terms

| Term | Meaning |
|---|---|
| `SCMEvent` | Normalized merged-PR event from feature 003, including repository scope, delivery identity, PR key, file list, diff handles, and timestamps. |
| `ChangeEvidence` | Immutable evidence record matching feature 004: `id`, `repository`, `source_scm_event_id`, `provider_delivery_id`, `normalized_pr_key`, `evidence_kind`, `source_path`, `diff_hunk_ref`, `before_value`, `after_value`, `observed_operation`, `parser`, `parser_version`, `immutable_hash`, `summary`, and `provenance`. Evidence is not rationale. |
| `StructuralChange` | Architecture-significant classification emitted by TH-02 producers using feature 004's serialized field set: `id`, `repository`, `source_scm_event_id`, `provider_delivery_id`, `normalized_pr_key`, `change_type`, `operation`, `affected_dependency`, `dependency_ecosystem`, `source_paths`, `evidence_ids`, `confidence`, `reason_code`, `adr_recommendation`, `classifier_name`, and `classifier_version`. For feature 005, `change_type` is `schema` or `api_contract` and dependency-specific fields remain present for byte-identical shape. |
| Schema change | A change to persisted data shape, migrations, ORM models, table/collection definitions, generated schema files, or validation contracts that alter stored data semantics. |
| API contract change | A change to externally or internally consumed interface contracts such as OpenAPI, GraphQL schemas, RPC/protobuf specs, public route signatures, request/response models, or status/error semantics. |
| Confidence | Numeric 0.0-1.0 signal summarizing classifier certainty, not approval. It informs downstream draft/review priority and threshold decisions. |
| Uncertainty note | Explicit explanation of why static evidence is limited, including generated artifacts, runtime reflection, framework convention, missing context, or ambiguous rename/add/remove semantics. |
| Threshold policy | Resolved default policy: `semantic-change-default-v1` routes candidates with `confidence >= 0.70` to draft-eligible `StructuralChange`; repositories may override the threshold. Candidates below threshold are retained as low-confidence `ChangeEvidence` / no-ADR-needed outcomes, not dropped. |

## User Stories

### [US-1] Detect database and schema changes — Priority: P1

**As a** structural-change workflow implementer, **I want** schema-related PR evidence classified separately from dependencies and APIs, **so that** storage-shape decisions can generate ADR candidates with correct semantics.

#### Acceptance Scenarios

- **Given** feature 003 evidence containing migration files, ORM model field changes, schema registry files, SQL DDL, or validation schema changes, **When** schema detection runs, **Then** it emits a `StructuralChange` with `change_type=schema`, schema-specific subtype, affected subject, evidence summary, and repository scope.
- **Given** a diff only touches seed data, tests, or comments without persisted shape changes, **When** schema detection runs, **Then** it records no-ADR-needed evidence or a low-confidence candidate according to the threshold policy.
- **Given** a generated migration or runtime-reflection pattern limits certainty, **When** classification completes, **Then** the output includes an uncertainty note rather than silently inflating confidence.

### [US-2] Detect API contract changes — Priority: P1

**As a** downstream ADR drafter, **I want** API contract changes classified distinctly from schema changes, **so that** generated ADRs discuss interface compatibility, consumers, and versioning rather than storage migration concerns.

#### Acceptance Scenarios

- **Given** evidence containing OpenAPI, GraphQL, protobuf, RPC, FastAPI route, request/response model, or public status/error shape changes, **When** API contract detection runs, **Then** it emits a `StructuralChange` with `change_type=api_contract`, API-specific subtype, affected contract subject, and cited evidence.
- **Given** an internal implementation-only route handler change with no visible request/response or public contract change, **When** API detection runs, **Then** it does not emit a high-confidence API contract change.
- **Given** generated API artifacts or dynamic framework routing obscure the true public contract, **When** classification completes, **Then** uncertainty is recorded explicitly.

### [US-3] Preserve a shared StructuralChange contract — Priority: P1

**As a** feature 008 implementer, **I want** schema/API and dependency classifiers to emit the same `StructuralChange` abstraction, **so that** ADR drafting can consume one producer interface.

#### Acceptance Scenarios

- **Given** a schema, API, or dependency classifier output, **When** feature 008 consumes it, **Then** the serialized `StructuralChange` and `ChangeEvidence` keys match feature 004 exactly without producer-specific branching.
- **Given** schema and API signals occur in the same PR, **When** classification runs, **Then** distinct `StructuralChange` records are emitted unless evidence proves one change is merely generated from the other.

### [US-4] Report confidence and explicit uncertainty — Priority: P1

**As a** tech lead reviewer, **I want** classification confidence and limitations shown honestly, **so that** I can decide whether to approve, edit, reject, or request more context.

#### Acceptance Scenarios

- **Given** strong direct evidence such as handwritten migration DDL or OpenAPI schema changes, **When** scoring runs, **Then** confidence is higher and evidence factors are explainable.
- **Given** only indirect evidence such as generated files, framework convention, or renamed files, **When** scoring runs, **Then** confidence is lower and uncertainty notes identify the limitation.
- **Given** confidence falls below the current threshold policy, **When** classification completes, **Then** the result is retained as evidence/no-ADR-needed telemetry and not silently discarded.

### [US-5] Apply the resolved confidence threshold policy — Priority: P1

**As a** product owner, **I want** schema/API classifier routing to use a conservative configurable default, **so that** MVP noise is controlled while downstream HITL review remains the authoritative filter.

#### Acceptance Scenarios

- **Given** no repository-specific override is configured, **When** schema/API classification runs, **Then** it uses `semantic-change-default-v1` with threshold `0.70`.
- **Given** a repository-specific override is configured, **When** schema/API classification runs, **Then** the override threshold is used and the policy version/threshold are recorded.
- **Given** classifier confidence is below threshold, **When** classification completes, **Then** the candidate is emitted as low-confidence `ChangeEvidence` / no-ADR-needed outcome and is not dropped.
- **Given** classifier confidence is at or above threshold, **When** classification completes, **Then** it emits a draft-eligible `StructuralChange` while feature 009 remains the authoritative approval/rejection filter.

### [US-6] Integrate with merged-PR evidence safely — Priority: P2

**As a** workflow operator, **I want** classifier integration to use feature 003 evidence without broad repository mining, **so that** detection remains replayable, minimal, and observable.

#### Acceptance Scenarios

- **Given** an `SCMEvent` and candidate evidence bundle, **When** classification runs, **Then** it reads changed-file metadata and diff summaries/handles only through the normalized evidence seam.
- **Given** observability records classifier outcomes, **When** metadata is exported, **Then** it excludes raw diffs, raw prompts, secrets, and full generated code content.

## Functional Requirements

- [FR-1] Consume the feature 004 shared `StructuralChange` and `ChangeEvidence` contract byte-identically at the serialized field level; do not create a second schema/API-specific contract.
- [FR-2] Define `SchemaChangeDetector` that classifies migration, DDL, ORM model, persisted validation schema, and schema registry evidence.
- [FR-3] Define `APIContractChangeDetector` that classifies OpenAPI, GraphQL, protobuf/RPC, route signature, request/response model, and public status/error semantics evidence.
- [FR-4] Keep schema and API classifications semantically distinct; do not collapse both into a generic structural bucket.
- [FR-5] Produce one or more `StructuralChange` records per `SCMEvent`, with one record per distinct affected subject/change type.
- [FR-6] Attach evidence summaries, file paths, diff hunk references or handles, extractor names, and limitation notes to every emitted change.
- [FR-7] Calculate confidence using explainable factors and include the threshold policy version and numeric threshold used; default is `semantic-change-default-v1` at `0.70` with per-repository override support.
- [FR-8] Preserve below-threshold outcomes as low-confidence `ChangeEvidence` / no-ADR-needed records for audit and HITL tuning without routing them as draft-eligible ADR candidates.
- [FR-9] Expose a classifier entry point usable by feature 015 workflow orchestration and feature 008 ADR drafting.
- [FR-10] Instrument metadata-only counts for schema/API candidates, no-ADR outcomes, uncertainty reasons, and threshold decisions through the observability port.

## Non-Functional Requirements

- [NFR-1] Classifiers are deterministic for the same `SCMEvent` evidence bundle and threshold policy.
- [NFR-2] Unit tests run without live GitHub, database, GraphQL server, OpenAPI generator, or LLM calls.
- [NFR-3] Detection does not fetch broad repository history or full unreferenced files; it stays within feature 003 evidence handles.
- [NFR-4] Raw diffs and source snippets are not exported to observability by default per `..\..\architecture.md#cross-cutting`.
- [NFR-5] The public classifier output shape remains stable for feature 008, even as individual detector heuristics evolve.

## Scope

### In Scope

- Schema and API-contract detection from merged-PR evidence.
- Shared `StructuralChange` / `ChangeEvidence` shape for TH-02 producers.
- Confidence scoring and explicit uncertainty notes.
- Threshold policy recording and configurable cutoff seam.
- Tests with deterministic fixtures for direct, ambiguous, generated, and no-ADR cases.

### Out of Scope

- Dependency manifest detection owned by feature 004.
- Claude ADR drafting, prompt generation, and rationale inference owned by feature 008.
- HITL review UI and approval decisions owned by features 009 and 010.
- Graph persistence, graph schema migration, and LlamaIndex adapter behavior owned by features 006 and 007.
- Live database introspection, running migrations, invoking API generators, or historical repository backfill.
- Azure DevOps implementation; provider neutrality is preserved through feature 003 contracts only.

## Themes, Metrics, and Failure Modes Served

- **Theme:** TH-02 Structural-Change & Intent Understanding.
- **MVP support:** Completes the non-dependency trigger classes in the MVP definition.
- **Success metrics:** Supports SM-01 by reducing noisy drafts, SM-02 by deterministic classifier latency, and SM-05 indirectly by keeping outputs non-authoritative until approval.
- **Failure modes addressed:** FM-03 threshold/noise control, FM-06 provisional inference, FM-07 static graph blind spots, FM-18 minimal evidence fetching, FM-19 PR summary overtrust, FM-21 trace hygiene.

## Dependencies

- **Project artifacts:** `..\..\architecture.md`, `..\..\domain-research.md`, `..\..\vision.md`, `..\..\feature-map.md`, `..\..\roadmap.md`.
- **Feature dependency:** 003 provides `SCMEvent`, candidate evidence, changed-file metadata, diff handles/summaries, repository scope, replay/dead-letter provenance, and observability seam.
- **Sibling alignment:** Feature 004 `spec.md` and `intent.md` were read. Feature 005 must reuse the feature 004 `StructuralChange` / `ChangeEvidence` serialized field set byte-identically and may only add schema/API semantics through existing shared fields and allowed values.
- **Downstream consumers:** 008 consumes emitted changes for ADR drafting; 015 invokes classifiers in the workflow; 013 observes quality; 009/010 present and approve downstream drafts.

## Success Criteria

- [ ] Schema and API contract classifiers produce distinct `StructuralChange` records.
- [ ] Outputs use the same serialized `StructuralChange` / `ChangeEvidence` field set defined by feature 004.
- [ ] Every emitted change includes feature 004 fields for repository scope, source event ids, provider delivery id, normalized PR key, source paths, evidence ids, confidence, reason code, `adr_recommendation`, classifier name/version, plus policy metadata in provenance/metadata.
- [ ] Low-confidence/no-ADR-needed outcomes are retained for tuning.
- [ ] Generated/runtime-limited artifacts produce explicit uncertainty notes.
- [ ] Classifiers are deterministic and covered by schema, API, mixed, generated, ambiguous, and no-change fixtures.

## Resolved Decisions and Assumptions

- **RD-005-1 Confidence threshold:** Resolved in autopilot mode. The default semantic/NLP change-detection threshold is configurable with per-repository override support and defaults to `0.70` (`semantic-change-default-v1`). Candidates below threshold are emitted as low-confidence `ChangeEvidence` / no-ADR-needed outcomes and are not dropped. Feature 009 HITL review remains the authoritative filter for draft approval/rejection.
- **RD-005-2 Conservative default assumption:** The `0.70` default is intentionally conservative for MVP to mitigate FM-03 ADR fatigue. It is not hardcoded in detectors; it belongs in a policy object/config seam and must be recorded with classifier outputs.
