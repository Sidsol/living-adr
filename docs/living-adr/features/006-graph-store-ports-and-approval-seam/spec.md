# Feature Specification: graph-store-ports-and-approval-seam

## Overview

Feature 006 defines LivingADR's stable connected-knowledge seam before any concrete graph adapter ships. It introduces typed write/read ports, graph value objects, ADR record repository expectations, adapter conformance requirements, and an `ApprovalBoundMutationService` contract that makes authoritative graph mutation impossible unless an `ApprovedReviewDecision` is supplied and validated.

This feature enables workflows, HITL, the future LlamaIndex adapter, and the MCP context server to depend on stable domain contracts rather than LlamaIndex internals. It also preserves the source-of-truth hierarchy: code and PR data are evidence, approved ADR records are authoritative rationale, and graph nodes/edges are queryable projections with citations.

## User Stories

### [US-1] Define graph value objects — Priority: P1
**As a** graph adapter implementer, **I want** stable value objects for nodes, edges, relationship labels, schema versions, snapshots, and query results, **so that** adapters and callers share one typed vocabulary.

#### Acceptance Scenarios
- **Given** a graph node, edge, or snapshot value is created without repository scope, **When** validation runs, **Then** construction fails before it can cross a port boundary.
- **Given** an unsupported relationship label is requested, **When** a caller builds a relationship, **Then** the type system or validation rejects it with a deterministic error.

### [US-2] Define ADR record repository expectations — Priority: P1
**As a** workflow developer, **I want** `ADRRecord` and `ADRRecordRepository` contracts, **so that** approved rationale can be stored as the authoritative record while graph entries remain projections.

#### Acceptance Scenarios
- **Given** an `ADRRecord` lacks an approved decision link or repository identity, **When** it is persisted, **Then** the repository contract rejects it.
- **Given** a graph node conflicts with an ADR record, **When** the source hierarchy is applied, **Then** the ADR record wins and the graph projection must be rebuilt or flagged.

### [US-3] Define write and read ports — Priority: P1
**As a** workflow or MCP implementer, **I want** `ArchitectureGraphStore` and `ArchitectureContextQuery` interfaces, **so that** write-side orchestration and read-only context delivery never depend on a concrete graph backend.

#### Acceptance Scenarios
- **Given** workflow code needs to upsert an approved ADR projection, **When** it calls the write port, **Then** every mutation method requires `RepositoryIdentity` and `ApprovedReviewDecision` arguments.
- **Given** MCP code answers a why question, **When** it uses the read port, **Then** it receives scoped ADR citations without mutation methods or write credentials.

### [US-4] Enforce approval-bound graph mutation — Priority: P1
**As a** tech lead, **I want** all graph writes routed through `ApprovalBoundMutationService`, **so that** unapproved model output, MCP requests, or workflow retries cannot mutate authoritative context.

#### Acceptance Scenarios
- **Given** a mutation request has `None`, a rejected decision, an expired-shaped decision, a repository mismatch, or a draft content-hash mismatch, **When** the service handles it, **Then** it raises before calling the graph adapter.
- **Given** a valid approved decision and matching mutation fingerprint, **When** the service handles the request, **Then** it delegates to the write port and emits metadata-only observability.

### [US-5] Provide adapter conformance surface — Priority: P1
**As a** future adapter owner, **I want** reusable conformance tests, **so that** LlamaIndex and later graph adapters prove repository scoping, approval enforcement, source hierarchy, and read/write separation.

#### Acceptance Scenarios
- **Given** a candidate adapter omits approval validation or repository filtering, **When** it runs the conformance suite, **Then** the suite fails with a named contract violation.
- **Given** a future adapter exposes LlamaIndex-specific objects through the port, **When** the conformance suite inspects returned values, **Then** it fails because concrete persistence details leaked.

### [US-6] Preserve dependency and source-of-truth boundaries — Priority: P1
**As a** downstream feature implementer, **I want** clear dependency rules, **so that** feature 007, 010, 012, and 015 can build against the seam without circular imports or authority confusion.

#### Acceptance Scenarios
- **Given** core graph ports are imported, **When** import checks run, **Then** no LlamaIndex, LangSmith, FastAPI, or MCP runtime dependency is imported by the core port modules.
- **Given** downstream code needs repository configuration or observability, **When** it uses this feature, **Then** it consumes `RepositoryIdentity` and `Observability` from feature 002 contracts.

## Functional Requirements

- [FR-1] Define typed core graph value objects: `NodeId`, `RelationshipType`, `GraphEdge`, `GraphSnapshotRef`, `SchemaVersion`, `MigrationResult`, `ConformanceReport`, `ADRRef`, `ADRPath`, `WhyAnswer`, and `ProvenancedADR`.
- [FR-2] Define `ADRRecord` and `ADRRecordRepository` expectations, including repository scope, decision linkage, status, content hash, provenance, and projection rebuild expectations.
- [FR-3] Define `ArchitectureGraphStore` write-side port matching the architecture sketch and requiring `RepositoryIdentity` on every method.
- [FR-4] Define `ArchitectureContextQuery` read-side port matching the architecture sketch and exposing no mutation methods.
- [FR-5] Define `ApprovedReviewDecision` contract fields needed by the mutation boundary, while leaving durable capability minting/consumption to feature 010.
- [FR-6] Define `ApprovalBoundMutationService` as the only write-path facade; it must validate approval, repository, content hash, and mutation fingerprint before calling `ArchitectureGraphStore`.
- [FR-7] Provide reusable adapter conformance tests and at least one in-memory/fake adapter fixture to prove the suite can catch violations.
- [FR-8] Ensure ports expose only LivingADR domain types and no concrete persistence, LlamaIndex, database, MCP, FastAPI, or LangSmith objects.

## Non-Functional Requirements

- [NFR-1] Type contracts must be stable enough for features 007, 010, 012, and 015 to implement without depending on concrete graph internals.
- [NFR-2] Graph write rejection must be deterministic and must avoid adapter calls on invalid approval.
- [NFR-3] Port modules must be dependency-light and safe for both workflow service and MCP context server imports.
- [NFR-4] Error names must be specific enough for audit and observability metadata without exporting raw drafts, diffs, or reviewer comments.
- [NFR-5] Repository scoping must be mandatory for every graph, ADR, and query contract.

## Out of Scope

- Implementing the LlamaIndex property graph adapter (feature 007).
- Implementing durable approval capability minting, one-shot consumption, TTL storage, and audit durability (feature 010), beyond defining the contract shape consumed by this seam.
- Implementing the MCP context server tools/resources (feature 012).
- Implementing LangGraph workflow orchestration/checkpointing (feature 015).
- Publishing ADR Markdown back to GitHub (feature 011).
- Building a production graph database, migrations beyond typed hooks, or external vector/embedding retrieval.

## Success Criteria

- [ ] All graph write methods require `RepositoryIdentity` and `ApprovedReviewDecision`.
- [ ] `ApprovalBoundMutationService` rejects mutation without a valid approved decision before adapter invocation.
- [ ] `ArchitectureContextQuery` is read-only and repository-scoped.
- [ ] `ADRRecordRepository` contract states ADR records are authoritative rationale and graph nodes/edges are projections.
- [ ] Reusable adapter conformance suite exists and documents how feature 007 adapters opt in.
- [ ] Port modules import no concrete graph persistence implementation.

## Open Questions

No blocking open questions remain for planning readiness. Non-blocking evolution points:

- Final relationship-label enum breadth may expand during feature 007; this feature should define the minimum stable set and an extension pattern.
- Durable idempotency and one-shot consumption semantics are finalized by feature 010; this feature only validates the approval shape and mutation fingerprint contract.
