# Codebase and Technical Research: llamaindex-property-graph-adapter

> **Scope note:** This is feature-level planning research for a greenfield project. `C:\repos\living-adr` is not present yet; current implementation facts come from project planning artifacts and dependency feature 006 contracts. External technical notes cover LlamaIndex PropertyGraphIndex and SQLite WAL behavior needed by this adapter.

## Architecture Overview

LivingADR is planned as a Python 3.12 single repository with two deployable processes: `workflow-service` for GitHub webhooks, LangGraph orchestration, HITL review, and approved graph mutation; and `mcp-context-server` for read-only IDE/assistant context delivery. The architecture explicitly places LlamaIndex behind `ArchitectureGraphStore` and `ArchitectureContextQuery` ports rather than allowing workflow or MCP code to depend on LlamaIndex internals.

Relevant anchors:

- `..\..\architecture.md#tech-stack`: LlamaIndex `PropertyGraphIndex` is the locked default graph implementation; graph persistence is under `var\graph`.
- `..\..\architecture.md#service-boundaries`: `ApprovalBoundMutationService` is the only write path, MCP uses read-only query port, and every graph method is repository-scoped.
- `..\..\architecture.md#data-model`: `ADRRecord` is canonical approved rationale; `ArchitectureGraph` is a versioned projection with repository identity on every node.
- `..\..\architecture.md#cross-cutting`: graph adapter owns schema versioning, extraction provenance, validation, rebuild, snapshot hooks, and conformance tests.
- `..\..\architecture.md#deployment`: PoC uses same-host single-writer SQLite WAL with workflow as writer and MCP as read-only reader.

## Directory Structure

Planned implementation repository from `..\..\architecture.md#tech-stack`:

```text
C:\repos\living-adr\
├── src\living_adr\
│   ├── core\                         # feature 006 ports and domain contracts
│   │   └── graph\                     # ArchitectureGraphStore / ArchitectureContextQuery
│   ├── graph\                         # default LlamaIndex adapter belongs here
│   ├── workflow_service\              # writer process, owns approved mutations
│   └── mcp_context_server\            # reader process, owns MCP tools/resources
├── tests\
│   ├── conformance\                   # feature 006 reusable graph conformance suite
│   ├── graph\                         # adapter-specific tests
│   └── fakes\
└── var\graph\                         # runtime persistence, not source-controlled
```

Current feature folder contains only `.gitkeep` before this planning pass. Feature 006 already plans the core port surface and conformance suite that this adapter must consume.

## Logic Flows

### Flow: Approved graph mutation through adapter
1. Entry point: workflow/HITL code calls `ApprovalBoundMutationService` after approval (`..\006-graph-store-ports-and-approval-seam\intent.md:11-20`).
2. Service validates `ApprovedReviewDecision`, repository, draft hash, and mutation fingerprint before adapter call (`..\..\architecture.md#service-boundaries`, lines 159-167 in source document).
3. Service delegates to `ArchitectureGraphStore` methods such as `upsert_adr_node`, `add_relationship`, `record_structural_change`, `supersede_adr`, or `retract_adr`.
4. `LlamaIndexPropertyGraphAdapter` maps domain DTOs to internal LlamaIndex property graph nodes/relations and persists them under repository-partitioned `var\graph` storage.
5. Adapter writes schema-version and provenance metadata with each projection; failed validation prevents current graph visibility.

### Flow: MCP read-only query
1. Entry point: `mcp-context-server` receives an IDE/assistant query and depends only on `ArchitectureContextQuery` (`..\..\architecture.md#service-boundaries`).
2. MCP passes `RepositoryIdentity` plus optional `GraphSnapshotRef` into `answer_why`, `traverse_from_code_area`, `fetch_adr`, or `list_adrs`.
3. Adapter opens a read snapshot or validates the current snapshot, executes bounded graph retrieval, and returns domain DTOs (`WhyAnswer`, `ADRPath`, `ProvenancedADR`, `ADRRef`).
4. No mutation methods, write credentials, LlamaIndex storage contexts, or SQLite handles are exposed to MCP.

### Flow: Schema governance and conformance
1. Adapter initialization derives a repository-safe persistence path under `var\graph`.
2. `current_schema_version(repository)` reads metadata; missing/unsupported metadata produces deterministic failure or migration requirement.
3. `migrate_schema(repository, target_version, decision)` performs approved schema migration behind 006's write port.
4. `check_conformance(repository)` verifies scope, schema hooks, snapshot hooks, provenance, relationship labels, and no backend leakage.
5. Feature 006's reusable conformance suite is run against the LlamaIndex adapter fixture.

## Data Models

### Model: Repository-scoped graph node
- Location: planned `src\living_adr\graph\llamaindex_adapter.py` and feature 006 `src\living_adr\core\graph\models.py`.
- Fields: domain `NodeId`, `RepositoryIdentity`, node kind/label, source ADR/evidence references, schema version, properties required by relationship traversal.
- Relationships: connected through typed `GraphEdge`/`RelationshipType`; each relationship must remain inside a repository scope unless a future feature explicitly supports federation.

### Model: Provenanced graph edge
- Location: planned graph adapter persistence mapping.
- Fields: from node, to node, relationship type, repository, source ADR id, evidence id/path, decision id, extraction method, extraction timestamp, schema version.
- Relationships: returned as part of `ADRPath` and citations for `WhyAnswer`.

### Model: Graph schema metadata
- Location: planned repository metadata record/file under `var\graph`.
- Fields: `SchemaVersion`, adapter name, created/updated timestamps, repository key, LlamaIndex persistence format version if available, migration history.
- Relationships: read by `current_schema_version`, `migrate_schema`, `check_conformance`, and snapshot validation.

### Model: Graph snapshot reference
- Location: feature 006 value object, implemented by this adapter.
- Fields: repository, snapshot id/revision, created timestamp, schema version, current/stale marker, optional persisted path or logical revision.
- Relationships: used by read methods to provide MCP-safe consistent reads.

## Integration Points

| Integration | Type | Location | Notes |
|---|---|---|---|
| Feature 006 `ArchitectureGraphStore` | Core write port | `src\living_adr\core\graph\ports.py` | Adapter must implement; no port changes. |
| Feature 006 `ArchitectureContextQuery` | Core read port | `src\living_adr\core\graph\ports.py` | Adapter must return domain DTOs only. |
| Feature 006 conformance suite | Test contract | `tests\conformance\graph_store_conformance.py` | Must pass against LlamaIndex adapter fixture. |
| LlamaIndex `PropertyGraphIndex` | Library | `src\living_adr\graph\...` | Provides graph construction/querying; internal-only. |
| LlamaIndex storage context | Library persistence | `var\graph\...` | `storage_context.persist(persist_dir=...)` and load-from-storage patterns exist in docs; path owned by adapter. |
| SQLite/WAL local persistence | File/database | `var\` and `var\graph` | Same-host single-writer rule; WAL readers and writer can coexist but only one writer at a time. |
| MCP context server | Read-side consumer | `src\living_adr\mcp_context_server\...` | Uses `ArchitectureContextQuery` only; no write handles. |

## LlamaIndex Property Graph Specifics

From the LlamaIndex PropertyGraphIndex documentation:

- A property graph is a set of labeled nodes with properties, connected by relationships into paths.
- `PropertyGraphIndex` provides graph construction and querying.
- Indexes can be persisted with `index.storage_context.persist(persist_dir="./storage")` and loaded with `StorageContext.from_defaults(persist_dir=...)` plus `load_index_from_storage(...)`.
- Existing graph stores can be loaded with `PropertyGraphIndex.from_existing(property_graph_store=..., vector_store=...)`.
- Graph construction applies `kg_extractors` to chunks and attaches entities/relations as metadata to LlamaIndex nodes.
- Default extractors are `SimpleLLMPathExtractor` and `ImplicitPathExtractor` if none are supplied.
- `SchemaLLMPathExtractor` supports allowed entity types, relation types, validation schema, and `strict=True`, which is directly relevant to FM-08/FM-10 mitigation.
- Retrieval can combine sub-retrievers such as `LLMSynonymRetriever`, `VectorContextRetriever`, and custom retrievers.
- `TextToCypherRetriever` is risky and not supported by simple stores; arbitrary generated Cypher should not be part of the PoC adapter boundary.

Research implication: the adapter should prefer schema-constrained extraction/validation and custom domain mapping over persisting arbitrary LLM-discovered path labels.

## SQLite WAL Specifics

From SQLite WAL documentation:

- WAL allows readers and a writer to proceed concurrently because writes append to a WAL file.
- There can still be only one writer at a time.
- All processes using a WAL database must be on the same host; WAL is not safe over a network filesystem because readers rely on shared-memory wal-index behavior.
- Readers see a consistent end mark for the duration of a transaction.
- WAL creates sidecar `-wal` and `-shm` files and requires checkpointing.
- Long-running readers can prevent checkpoint progress; busy timeout/retry behavior matters for MCP reads.
- Read-only WAL opens are possible only under specific sidecar/immutable conditions, so the PoC design should validate actual read-only open behavior in tests.

Research implication: this feature should not promise multi-host graph sharing; it should implement same-host, single-writer, short-read-transaction behavior and expose snapshots/stale results through the port.

## Configuration & Environment

Expected configuration from architecture:

- Graph persistence root defaults under `var\graph`.
- Repository identity comes from feature 002 `living-adr.config.yaml` and must determine graph partitioning.
- Workflow service opens persistence read/write; MCP opens read-only/snapshot view.
- No new secrets are required for graph persistence.
- External graph database configuration is out of scope for MVP.

## Technical Debt & Observations

- The project is greenfield; no implementation files exist yet, so file-level research is based on planned architecture and feature 006 contracts.
- LlamaIndex extraction defaults can produce unconstrained paths; this is a direct false-edge risk unless schema-constrained extraction and validation are used.
- LlamaIndex persistence APIs are library-specific; leaking storage context, retrievers, graph store classes, or nodes through ports would violate the swap seam.
- SQLite WAL read-only behavior has platform/path caveats; adapter tests should verify actual local behavior instead of relying on assumptions.
- Feature 010 owns durable capability consumption, so this adapter should not implement its own approval-token lifecycle beyond honoring 006 method signatures and validation expectations.

## Key Patterns

- Port-and-adapter boundary: core owns contracts; `graph` package owns LlamaIndex implementation.
- Repository scope is mandatory on every persisted object and every query.
- Approved ADR records are authoritative; graph nodes/edges are projections with citations.
- Single writer: workflow service writes; MCP reads via read-only query/snapshot path.
- Conformance-first adapter validation: feature 006 suite is the executable contract.
- Strict schema and provenance mitigate FM-08 graph drift and FM-10 false edges.