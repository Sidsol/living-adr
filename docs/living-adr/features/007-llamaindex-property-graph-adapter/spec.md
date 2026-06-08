# Feature Specification: llamaindex-property-graph-adapter

## Overview

Feature 007 implements LivingADR's default `LlamaIndexPropertyGraphAdapter` behind the feature 006 graph ports. It provides repository-scoped property-graph persistence under `var\graph`, schema-version metadata, provenance on every extracted entity and relationship, read snapshots for the MCP server, and adapter tests proving compliance with 006's reusable conformance suite.

This feature does **not** redefine `ArchitectureGraphStore`, `ArchitectureContextQuery`, `ApprovalBoundMutationService`, `RepositoryIdentity`, `ADRRecord`, or `ApprovedReviewDecision`. It implements those contracts and keeps LlamaIndex internals behind the adapter boundary.

## User Stories

### [US-1] Persist a repository-scoped property graph — Priority: P1
**As a** workflow-service implementer, **I want** approved ADR projections stored through `ArchitectureGraphStore`, **so that** LivingADR has durable connected architecture knowledge without exposing LlamaIndex internals.

#### Acceptance Scenarios
- **Given** an approved ADR projection for repository A, **When** the adapter upserts its ADR node, **Then** the persisted node includes repository identity, stable domain node id, schema version, ADR metadata, and no cross-repository leakage.
- **Given** repository A and repository B contain the same ADR id or code-area label, **When** either repository is queried, **Then** only nodes scoped to that `RepositoryIdentity` are returned.

### [US-2] Record schema-version metadata and migrations — Priority: P1
**As a** graph maintainer, **I want** explicit graph schema version metadata and migration hooks, **so that** property-graph drift is detected and controlled.

#### Acceptance Scenarios
- **Given** a repository graph is initialized, **When** `current_schema_version(repository)` runs, **Then** it returns the adapter-supported schema version stored with the graph metadata.
- **Given** persisted graph metadata is missing or unsupported, **When** the adapter opens the graph, **Then** it fails deterministically or returns a migration result instead of silently reading stale structures.

### [US-3] Maintain SQLite/WAL-compatible local persistence — Priority: P1
**As a** PoC operator, **I want** graph files under `var\graph` to follow the single-writer plus WAL-compatible local persistence model, **so that** workflow writes and MCP reads can coexist on one host.

#### Acceptance Scenarios
- **Given** the workflow service is the only writer, **When** it initializes the adapter, **Then** the persistence path is repository-partitioned under `var\graph` and uses SQLite-compatible settings with WAL/read-only reader expectations where SQLite state is used.
- **Given** the MCP server opens a read snapshot, **When** a workflow write is in progress, **Then** the read path either observes a consistent prior snapshot or returns a retryable busy/stale-snapshot result without mutating graph state.

### [US-4] Preserve provenance for extracted entities and edges — Priority: P1
**As a** reviewer or MCP user, **I want** every entity and relationship to cite approved ADR/evidence sources, **so that** false edges can be audited and corrected.

#### Acceptance Scenarios
- **Given** the adapter extracts component, dependency, schema, API, PR, commit, or evidence entities from an approved ADR projection, **When** it persists nodes and relationships, **Then** each record includes source ADR id, evidence id/path, extraction method, extraction timestamp, and decision id.
- **Given** a graph path is returned for a why-answer, **When** the caller inspects the path, **Then** every edge has provenance sufficient to trace back to approved rationale or source evidence.

### [US-5] Provide read snapshots for MCP context delivery — Priority: P1
**As an** MCP context-server implementer, **I want** stable read snapshots through `ArchitectureContextQuery`, **so that** IDE/assistant queries can answer with approved citations without write credentials.

#### Acceptance Scenarios
- **Given** an MCP query calls `answer_why`, `fetch_adr`, `list_adrs`, or `traverse_from_code_area`, **When** it passes a repository and optional snapshot, **Then** returned values are domain DTOs with ADR citations and no LlamaIndex objects.
- **Given** a snapshot reference is stale or absent, **When** `validate_snapshot_current` runs, **Then** it returns a deterministic current/stale answer without performing writes.

### [US-6] Pass the feature 006 adapter conformance suite — Priority: P1
**As a** graph adapter owner, **I want** the LlamaIndex adapter tested against the reusable conformance suite, **so that** it honors repository scoping, approval enforcement, read/write separation, schema hooks, and no-backend-leak constraints.

#### Acceptance Scenarios
- **Given** the adapter test factory is wired to 006's conformance suite, **When** the suite runs, **Then** all required write/read port, approval, scope, and leakage tests pass.
- **Given** an invalid approval decision reaches the adapter through direct tests, **When** mutation is attempted, **Then** the adapter rejects or relies on the service contract without persisting partial graph state.

### [US-7] Mitigate graph drift and false edges — Priority: P1
**As a** tech lead, **I want** strict relationship labels, validation, and repair hooks, **so that** GraphRAG false edges and property-graph schema drift do not degrade trusted architecture answers.

#### Acceptance Scenarios
- **Given** LlamaIndex extractors suggest unsupported entity or relationship types, **When** validation runs, **Then** invalid paths are rejected, quarantined, or returned as non-authoritative diagnostics rather than persisted as approved graph edges.
- **Given** graph validation finds orphaned nodes, missing provenance, repository mismatch, or schema-version mismatch, **When** `check_conformance(repository)` runs, **Then** it reports named failures with enough metadata to rebuild or repair the projection.

## Functional Requirements

- [FR-1] Implement `LlamaIndexPropertyGraphAdapter` as the default adapter for feature 006's `ArchitectureGraphStore` and `ArchitectureContextQuery` ports.
- [FR-2] Persist graph data under `var\graph` using repository-safe partitioning and deterministic path derivation from `RepositoryIdentity`.
- [FR-3] Store graph schema version metadata per repository and implement `current_schema_version`, `migrate_schema`, `rebuild_snapshot`, and `check_conformance` hooks.
- [FR-4] Ensure every persisted node and edge carries repository scope and cannot be read from another repository's query.
- [FR-5] Record provenance on extracted entities and edges: source ADR, source evidence, decision id, extraction method, extraction timestamp, and schema version.
- [FR-6] Provide read-side query methods returning `ADRPath`, `WhyAnswer`, `ProvenancedADR`, and `ADRRef` domain DTOs only.
- [FR-7] Support MCP-safe snapshots through `GraphSnapshotRef` and `validate_snapshot_current` without exposing write handles.
- [FR-8] Run and pass feature 006's adapter conformance suite using a real LlamaIndex-backed adapter fixture.
- [FR-9] Add adapter-specific tests for persistence reopen, repository isolation, provenance completeness, schema mismatch handling, WAL/single-writer expectations, and no LlamaIndex leakage.
- [FR-10] Use schema-constrained extraction/validation rather than persisting arbitrary LLM-generated paths.

## Non-Functional Requirements

- [NFR-1] Public adapter methods must expose only LivingADR domain types and standard scalar/collection types; no LlamaIndex, SQLite connection, retriever, or storage context objects cross port boundaries.
- [NFR-2] Writes must be transactional at the adapter boundary where the backing permits it; failed relationship/node writes must not leave partially approved graph projections visible as current.
- [NFR-3] Local PoC persistence must respect single-writer plus WAL-compatible same-host constraints from `..\..\architecture.md#deployment`.
- [NFR-4] Read queries must be deterministic, repository-scoped, bounded by configured limits, and safe for the read-only MCP process.
- [NFR-5] Drift/false-edge diagnostics must be specific enough for audit and repair without exporting raw private repository text by default.
- [NFR-6] Tests must be runnable with existing project tools (`uv run pytest`, `uv run ruff check`) and must not require an external graph database.

## Out of Scope

- Redefining feature 006 graph ports, value objects, conformance contracts, or `ApprovalBoundMutationService`.
- Implementing durable approval capability minting, one-shot consumption storage, or audit durability owned by feature 010.
- Implementing MCP server tools/resources owned by feature 012.
- Implementing LangGraph workflow orchestration/checkpointing owned by feature 015.
- Implementing Claude ADR drafting or structural-change detection owned by features 004, 005, and 008.
- Adding Neo4j, RDF, Postgres, or server-hosted graph backends.
- Historical backfill or broad repository mining beyond approved ADR projections supplied through the ports.

## Success Criteria

- [ ] `LlamaIndexPropertyGraphAdapter` implements feature 006's `ArchitectureGraphStore` and `ArchitectureContextQuery` without port changes.
- [ ] Feature 006's conformance suite passes against the LlamaIndex adapter fixture.
- [ ] Repository-scoped nodes and queries prevent cross-repository reads and writes.
- [ ] Schema-version metadata is persisted and checked on open/query/migration paths.
- [ ] Graph persistence lives under `var\graph` with same-host single-writer/WAL-compatible assumptions documented and tested where applicable.
- [ ] Every node and edge created from extracted entities/relationships includes provenance and approved decision linkage.
- [ ] MCP read snapshots return domain DTOs with citations and expose no mutation/write handles.
- [ ] Drift and false-edge validation failures are detectable through `check_conformance` or adapter-specific diagnostics.

## Open Questions

No blocking open questions remain for planning readiness. Non-blocking implementation decisions:

- Which LlamaIndex local graph store class is selected by scaffolded dependencies for PoC persistence; implementers should prefer the smallest local persistent option available in llama-index 0.14.22 and keep it behind the adapter.
- Whether `rebuild_snapshot` copies persisted graph files or records a stable logical revision first; either is acceptable if MCP reads remain consistent and port semantics are preserved.