# Feature Specification: dependency-change-detection

## Overview

Feature 004 is the first production `StructuralChange` producer for LivingADR. It consumes Feature 003's normalized merged-PR `SCMEvent` and immutable candidate evidence stream, detects dependency-manifest and lockfile changes, and emits repository-scoped `StructuralChange` plus immutable `ChangeEvidence` records for downstream ADR drafting.

The feature focuses only on dependency evidence so it can ship before schema/API classifiers. It supports TH-02 Structural-Change & Intent Understanding, mitigates ADR fatigue by producing explicit no-ADR-needed outcomes below threshold, and unblocks Feature 008 (`claude-adr-drafting-capability`) with the first usable structural-change contract.

## Canonical Terms

| Term | Meaning |
|---|---|
| `SCMEvent` | Feature 003 provider-neutral, repository-scoped merged-PR event envelope with provider delivery identity, normalized PR key, timestamps, and fetch handles. |
| Candidate evidence | Feature 003 immutable PR metadata, changed files, diff summary/handle, and provenance available to classifiers. Evidence is not approved rationale. |
| `DependencyChangeClassifier` | Deterministic core service that inspects candidate evidence for dependency manifest/lockfile changes and emits classification outcomes. |
| Dependency manifest | Source file declaring direct dependencies, e.g. `pyproject.toml`, `requirements*.txt`, `package.json`, `pom.xml`, `build.gradle`, `go.mod`, `Cargo.toml`, `Gemfile`, `.csproj`. |
| Lockfile | Resolved dependency graph file, e.g. `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`, `uv.lock`, `Pipfile.lock`, `go.sum`, `Cargo.lock`, `Gemfile.lock`. |
| Direct dependency | Dependency declared by a manifest. Direct dependency additions/removals are stronger architecture signals than transitive-only lockfile churn. |
| Transitive-only change | Lockfile change where no direct manifest dependency changed; usually below ADR threshold unless paired with strong evidence. |
| `StructuralChange` | Repository-scoped classified architecture-significant change. This feature defines `change_type="dependency"` records with confidence and source evidence references. |
| `ChangeEvidence` | Immutable evidence record produced from SCM evidence and classifier observations, including source paths, diff hunks/summary references, provenance, and redaction-safe summary. |
| No-ADR-needed outcome | Deterministic outcome recorded when dependency signal is below the configured threshold; downstream drafting must not run for that outcome. |

## User Stories

### [US-1] Detect dependency manifest additions and removals — Priority: P1

**As a** structural-change workflow, **I want** direct dependency additions/removals detected from merged-PR evidence, **so that** architecture-significant dependency decisions can trigger ADR drafting.

#### Acceptance Scenarios

- **Given** Feature 003 candidate evidence for a merged PR that changes `package.json` by adding a direct dependency, **When** classification runs, **Then** it emits one `StructuralChange` with `change_type="dependency"`, `operation="added"`, confidence at or above threshold, and source path `package.json`.
- **Given** a merged PR changes `pyproject.toml` by removing a direct dependency, **When** classification runs, **Then** it emits a dependency `StructuralChange` with `operation="removed"`, affected package name, confidence, and immutable `ChangeEvidence` linked to the `SCMEvent`.
- **Given** a manifest and lockfile are both changed for the same direct dependency, **When** evidence is normalized, **Then** the classifier deduplicates the signal into one change with both source paths and evidence references.

### [US-2] Normalize dependency evidence for downstream drafting — Priority: P1

**As a** Claude ADR drafting node, **I want** stable `StructuralChange` and `ChangeEvidence` contracts, **so that** drafting can cite concrete files and avoid inventing rationale.

#### Acceptance Scenarios

- **Given** a dependency change classification, **When** the result is serialized for the workflow, **Then** `StructuralChange` includes repository, structural change id, source SCM event id, normalized PR key, change type, operation, package/ecosystem, source paths, confidence, evidence ids, and `adr_recommendation`.
- **Given** evidence is persisted, **When** a downstream consumer reads it, **Then** `ChangeEvidence` is immutable and includes repository, evidence id, source SCM event id, provider delivery id, source path, diff range or hunk reference when available, observed before/after values, evidence kind, and provenance.
- **Given** Feature 008 receives a dependency `StructuralChange`, **When** it packages a prompt, **Then** it can cite file paths and evidence summaries without reading raw GitHub payloads or treating evidence as approved rationale.

### [US-3] Suppress low-signal dependency churn — Priority: P1

**As a** tech lead, **I want** transitive-only or ambiguous dependency churn to produce no-ADR-needed outcomes, **so that** LivingADR does not create ADR fatigue.

#### Acceptance Scenarios

- **Given** a PR changes only a lockfile with many transitive version bumps and no manifest dependency change, **When** classification runs, **Then** it records a deterministic no-ADR-needed outcome below threshold and emits no draft-eligible `StructuralChange`.
- **Given** a changed file resembles a dependency file but cannot be parsed or mapped to an ecosystem, **When** classification runs, **Then** it records an uncertain no-ADR-needed outcome with failure reason and source path rather than failing the whole workflow.
- **Given** below-threshold outcomes are persisted, **When** observability or replay inspects the run, **Then** the reason code and confidence are available without exporting raw diffs.

### [US-4] Keep classification deterministic and replayable — Priority: P1

**As a** platform operator, **I want** dependency classification to be pure, deterministic, and replay-safe, **so that** replaying Feature 003 evidence yields the same structural-change/no-ADR decision.

#### Acceptance Scenarios

- **Given** identical `SCMEvent` and candidate evidence inputs, **When** classification runs multiple times or through replay, **Then** it produces the same outcome ids, confidence, reason codes, and source path ordering.
- **Given** malformed evidence, missing diff handles, or unsupported manifest formats, **When** classification runs, **Then** it returns a typed uncertain/no-ADR outcome without raising unhandled exceptions.
- **Given** observability records classification metrics, **When** traces are exported, **Then** only metadata such as repository key, PR key, change class, confidence, reason code, and source path list is emitted.

### [US-5] Integrate as the first structural-change producer — Priority: P1

**As a** LangGraph workflow implementer, **I want** a stable producer port for dependency changes, **so that** Feature 008 can consume dependency `StructuralChange` records before Feature 005 exists.

#### Acceptance Scenarios

- **Given** the workflow receives Feature 003 evidence, **When** the dependency classifier is invoked, **Then** it returns a typed `DependencyClassificationResult` containing draft-eligible changes and no-ADR-needed outcomes.
- **Given** Feature 005 adds schema/API classifiers later, **When** they emit structural changes, **Then** they can reuse the same `StructuralChange`/`ChangeEvidence` abstractions without dependency-specific leakage.
- **Given** the classifier emits a draft-eligible change, **When** downstream orchestration checks readiness for Feature 008, **Then** the record contains enough evidence references for Claude drafting without requiring direct SCM API calls.

## Functional Requirements

- [FR-1] Consume Feature 003 `SCMEvent` plus candidate evidence; do not read raw GitHub webhook payloads.
- [FR-2] Identify known dependency manifests and lockfiles by normalized path and filename patterns.
- [FR-3] Parse or diff dependency manifests for direct dependency additions, removals, and version-range changes for supported ecosystems.
- [FR-4] Treat manifest-backed direct additions/removals as draft-eligible when confidence meets the configured threshold.
- [FR-5] Treat lockfile-only/transitive-only churn as no-ADR-needed by default unless a supported rule explicitly raises confidence.
- [FR-6] Emit immutable `ChangeEvidence` records for every source path used by a classification or no-ADR decision.
- [FR-7] Emit `StructuralChange` records for draft-eligible dependency changes with confidence, source paths, evidence ids, and `adr_recommendation="draft"`.
- [FR-8] Emit no-ADR-needed outcomes for below-threshold or uncertain signals with confidence and reason codes.
- [FR-9] Keep classification deterministic: stable ordering, stable ids derived from repository/event/path/package/operation, no LLM calls, no live SCM calls.
- [FR-10] Provide isolated unit tests for manifest matching, parsing, confidence scoring, evidence normalization, no-ADR decisions, and replay determinism.
- [FR-11] Expose a structural-change producer interface reusable by later schema/API classifiers.
- [FR-12] Instrument classification through the inherited `Observability` port with metadata-only trace discipline.

## Non-Functional Requirements

- [NFR-1] Determinism: identical evidence inputs produce byte-for-byte stable serialized outputs except timestamps explicitly provided by the input.
- [NFR-2] Testability: all classifier behavior is testable with local fixtures and fake evidence; no live GitHub, Claude, graph, or LangGraph runtime is required.
- [NFR-3] Security: repository text and diffs are untrusted; no model/tool execution occurs in this feature.
- [NFR-4] Trace hygiene: raw diffs, dependency file contents, prompts, and secrets are not exported to observability.
- [NFR-5] ADR-fatigue control: below-threshold changes must be explicit, persisted, and blocked from draft generation.
- [NFR-6] Extensibility: dependency-specific fields must not pollute the generic structural-change interface used by Feature 005 and Feature 008.

## In Scope

- Dependency manifest and package-lock style evidence from merged PRs.
- Python, JavaScript/TypeScript, Go, Rust, JVM, Ruby, and .NET manifest/lockfile filename recognition at planning level.
- Direct dependency add/remove/version-range signal extraction where evidence contains enough before/after or diff summary detail.
- Confidence scoring and no-ADR-needed outcomes.
- Immutable evidence and structural-change contract definitions for Feature 008.
- Deterministic fixture-based tests.

## Out of Scope

- Schema/database change detection and API contract detection (Feature 005).
- Claude calls, prompt engineering, ADR drafting, and human review (Features 008–010).
- Graph persistence implementation and approved graph mutation (Features 006–007 and 010).
- Fetching additional repository history or live SCM content beyond Feature 003 evidence.
- Vulnerability, license, or dependency health analysis beyond classifying that a dependency changed.
- Package-manager-specific full lockfile semantic resolution when direct manifest evidence is absent.

## Dependencies

- **Project artifacts:** `..\..\architecture.md`, `..\..\domain-research.md`, `..\..\vision.md`, `..\..\feature-map.md`, `..\..\roadmap.md`.
- **Feature dependency:** Feature 003 `github-webhook-ingestion` supplies normalized `SCMEvent`, `SCMProvider` fetch handles, and immutable candidate evidence linked to provider delivery id and normalized PR key.
- **Downstream consumers:** Feature 008 consumes draft-eligible dependency `StructuralChange` + `ChangeEvidence`; Feature 005 reuses generic contracts; Feature 015 invokes the producer in the workflow.
- **Architecture anchors:** `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#anti-patterns`.

## Success Criteria

- [ ] Dependency manifest additions/removals produce draft-eligible `StructuralChange` records with confidence and source paths.
- [ ] Immutable `ChangeEvidence` records are emitted for each supporting source path and linked to `SCMEvent` and provider delivery id.
- [ ] Lockfile-only/transitive-only churn produces deterministic no-ADR-needed outcomes below threshold.
- [ ] Classification is deterministic under replay and covered by fixture-based tests.
- [ ] Feature 008 can consume the emitted contract without reading raw GitHub payloads or live SCM APIs.
- [ ] Observability emits metadata-only classification telemetry.

## Open Questions

- The exact numeric default confidence threshold remains an architecture open question; this plan assumes `0.70` for draft eligibility and makes it configurable/tested.
- The exact persisted storage table names may be adjusted by Feature 015/006 implementation, but the domain contract fields are stable for downstream consumers.
