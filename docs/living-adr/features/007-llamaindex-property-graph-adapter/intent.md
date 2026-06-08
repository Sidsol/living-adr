# Architecture Intent: llamaindex-property-graph-adapter

## Current State

LivingADR is a greenfield project with architecture and feature planning artifacts but no `C:\repos\living-adr` implementation yet. Feature 006 defines the stable graph seam: `ArchitectureGraphStore`, `ArchitectureContextQuery`, core graph value objects, `ADRRecordRepository`, `ApprovedReviewDecision`, `ApprovalBoundMutationService`, and a reusable adapter conformance suite. Feature 007 must implement the default adapter behind those contracts.

The architecture requires LlamaIndex PropertyGraphIndex as the default graph/retrieval implementation behind internal ports (`..\..\architecture.md#tech-stack`), read/write service separation and repository-scoped graph calls (`..\..\architecture.md#service-boundaries`), approved ADR records as canonical rationale with graph projections as versioned citations (`..\..\architecture.md#data-model`), graph adapter ownership of schema versioning/provenance/validation/rebuild/snapshot hooks (`..\..\architecture.md#cross-cutting`), and same-host single-writer SQLite WAL local persistence (`..\..\architecture.md#deployment`).

## Desired State

After this feature, `LlamaIndexPropertyGraphAdapter` is the default implementation of feature 006's graph write/read ports. It persists repository-scoped property graph data under `var\graph`, records schema-version metadata, validates and stores provenance on extracted entities and edges, provides MCP-safe read snapshots, and passes 006's conformance suite without changing the port shape.

The adapter internalizes all LlamaIndex details. Workflow code sees only `ArchitectureGraphStore` through `ApprovalBoundMutationService`; MCP code sees only `ArchitectureContextQuery`; neither receives LlamaIndex nodes, retrievers, storage contexts, SQLite handles, or path-specific implementation objects.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Adapter implementation | Feature 006 defines ports only | Default `LlamaIndexPropertyGraphAdapter` implements both ports | Create graph adapter package and tests |
| Repository scope | Required by ports and architecture | Every persisted node/edge/query is partitioned and filtered by `RepositoryIdentity` | Define path derivation, metadata fields, and isolation tests |
| Persistence | Architecture says `var\graph`; no implementation | Durable local LlamaIndex persistence with same-host WAL-compatible expectations | Implement storage factory/open modes and reopen tests |
| Schema versioning | Required by architecture | Per-repository schema metadata with migration/current-version hooks | Add metadata store, version checks, deterministic mismatch behavior |
| Provenance | Required for graph governance | Every extracted node/edge records ADR/evidence/decision/extraction provenance | Define provenance mapper and validation tests |
| MCP snapshots | Port includes snapshot refs | Read-only query methods operate on current or explicit snapshot refs | Implement snapshot references and validation semantics |
| Conformance | 006 suite planned | LlamaIndex fixture passes conformance plus adapter-specific tests | Wire test factory and address failures without changing ports |
| Drift/false edges | FM-08/FM-10 identified | Strict schema/relationship validation rejects unsupported paths | Use schema-constrained extraction/mapping and conformance diagnostics |

## Architecture Options

### Option A: Expose LlamaIndex directly to workflow and MCP
**Approach:** Instantiate `PropertyGraphIndex` where needed and let workflow/MCP call LlamaIndex APIs directly.

- ✅ Pros: Fastest prototype; minimal adapter code.
- ❌ Cons: Violates `..\..\architecture.md#service-boundaries`, breaks graph swappability, exposes write-capable internals to MCP risk boundary, bypasses 006 conformance, and increases graph drift/false-edge risk.
- 🔧 Effort: Low now, very high later.

### Option B: Thin adapter around LlamaIndex persistence only
**Approach:** Implement port methods as simple wrappers over LlamaIndex save/load/query APIs with minimal schema/provenance handling.

- ✅ Pros: Keeps callers off direct LlamaIndex imports; moderate implementation size.
- ❌ Cons: Under-specifies schema-version metadata, provenance, snapshots, WAL/open-mode behavior, and false-edge validation; likely fails meaningful conformance and future MCP trust requirements.
- 🔧 Effort: Medium.

### Option C: Domain-first adapter with explicit mapping, metadata, provenance, snapshots, and conformance (selected)
**Approach:** Build `LlamaIndexPropertyGraphAdapter` as a domain boundary: map 006 DTOs to LlamaIndex internals, persist repository-partitioned graph state, maintain schema metadata/provenance, validate relationship/entity schema, expose snapshot-aware read DTOs, and run 006 conformance plus adapter-specific tests.

- ✅ Pros: Satisfies architecture anchors, protects the swap seam, mitigates FM-08/FM-10, gives MCP a read-only domain surface, and creates executable confidence for downstream features 008, 010, and 012.
- ❌ Cons: More implementation work; requires careful testing around local persistence and LlamaIndex version behavior.
- 🔧 Effort: High.

## Selected Approach

**Option C: Domain-first adapter with explicit mapping, metadata, provenance, snapshots, and conformance.**

Rationale: This feature is the primary TH-04 storage/retrieval adapter and sits on the critical path `002 → 006 → 007 → 008 → 009 → 010 → 011`. A thin wrapper would satisfy nominal persistence but not the architectural risks that caused 007 to be split out: property-graph drift, false edges, schema governance, and read/write trust separation. Option C is the only approach that implements feature 006's ports, respects `..\..\architecture.md#deployment` single-writer/WAL constraints, and preserves approved ADR records as authority while graph data remains a cited projection.

## Module Surface Analysis

| Module | Inputs | Callers | Deletion test | Isolated-test candidate |
|---|---:|---|---|---|
| `src\living_adr\graph\__init__.py` | Adapter class exports | workflow service bootstrap, MCP bootstrap, tests | Deleting forces unstable deep imports | Yes — import/export test only |
| `src\living_adr\graph\llamaindex_adapter.py` | `RepositoryIdentity`, `ADRRecord`, graph DTOs, decisions, persistence config | `ApprovalBoundMutationService`, MCP query wiring, tests | Deleting removes default graph backend | Yes — with temp project-local fixture paths |
| `src\living_adr\graph\llamaindex_mapping.py` | Domain graph DTOs, ADR records, structural changes | adapter | Deleting mixes domain/LlamaIndex conversion into adapter methods | Yes — pure mapping tests with fake LlamaIndex-like values if needed |
| `src\living_adr\graph\schema.py` | schema version, allowed entity/relationship labels | adapter, tests | Deleting allows silent schema drift | Yes — pure validation tests |
| `src\living_adr\graph\provenance.py` | ADR/evidence/decision/extraction metadata | mapping, adapter | Deleting makes false-edge audits impossible | Yes — pure completeness tests |
| `src\living_adr\graph\persistence.py` | repository identity, graph root path, open mode | adapter bootstrap | Deleting scatters path/open-mode/WAL rules | Yes — filesystem tests under repo-local test workspace |
| `src\living_adr\graph\snapshots.py` | repository, schema metadata, logical/persisted revisions | adapter read methods | Deleting leaves MCP without consistent read refs | Yes — snapshot state tests |
| `tests\graph\test_llamaindex_adapter_conformance.py` | adapter factory | CI/conformance | Deleting removes proof that 007 honors 006 | No — test file itself |
| `tests\graph\test_llamaindex_adapter_persistence.py` | adapter fixture, repo-local storage | adapter developers | Deleting misses reopen/WAL/scope regressions | No — integration-style test |
| `tests\graph\test_llamaindex_adapter_queries.py` | seeded approved graph | MCP/downstream confidence | Deleting misses read DTO/snapshot regressions | No — integration-style test |
| `tests\graph\test_llamaindex_adapter_validation.py` | invalid labels/provenance/schema | adapter developers | Deleting misses FM-08/FM-10 guardrails | No — integration-style test |

## Anti-Patterns to Avoid

- **Port redefinition:** Changing 006's contracts to fit LlamaIndex would invert the dependency and break downstream planning.
- **LlamaIndex leakage:** Returning LlamaIndex nodes, retrievers, storage contexts, graph stores, or SQLite handles through domain ports violates the swap seam.
- **Graph as authority:** Treating extracted graph paths as approved rationale contradicts `..\..\architecture.md#data-model`; graph paths must cite approved ADR/evidence.
- **Arbitrary LLM path persistence:** Default or unconstrained extractors can create false edges; unsupported labels must be rejected/quarantined.
- **Cross-repository shared graph namespace:** Same names in different repos must not collide or appear in another repository's answer.
- **MCP read path with write handles:** The MCP server must not receive adapter mutation methods, writable storage contexts, SCM credentials, or approval services.
- **Multi-host WAL assumptions:** SQLite WAL is a same-host pattern; do not design `var\graph` sharing over network filesystems.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add default graph adapter package, schema/provenance/persistence/snapshot helpers, conformance fixture, and adapter-specific tests | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LlamaIndex local persistence API differs from assumptions in 0.14.22 | Medium | High | Encapsulate all library calls in `llamaindex_adapter.py`/`persistence.py`; write reopen tests; avoid exposing library types. |
| Adapter passes nominal conformance but loses provenance | Medium | High | Add adapter-specific provenance completeness tests and make missing provenance a validation failure. |
| Schema drift from new relationship labels | Medium | High | Centralize schema in `graph\schema.py`; require migration/version bump for changes; report mismatches via `check_conformance`. |
| False edges from extractor output | Medium | High | Prefer `SchemaLLMPathExtractor`/strict validation or deterministic mapping from approved ADR structures; quarantine unsupported paths. |
| MCP reads see partial writes | Medium | Medium | Use workflow single-writer discipline, short transactions, snapshot refs, and retryable stale/busy handling. |
| Repository path collisions or unsafe path names | Low | High | Derive storage paths from normalized repository key plus opaque repo id/hash; test collision cases. |
| Durable approval semantics duplicated from feature 010 | Medium | Medium | Consume 006 `ApprovedReviewDecision` only; leave one-shot persistence/audit durability to feature 010. |