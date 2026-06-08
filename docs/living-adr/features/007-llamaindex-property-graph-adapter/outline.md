# Implementation Outline: llamaindex-property-graph-adapter

## Slice Strategy

The feature is decomposed into seven vertical slices matching the feature-map estimate. The sequence starts with adapter skeleton and repository-scoped persistence, then adds schema metadata, provenance/validation, write-port behavior, read snapshots/query behavior, conformance execution, and final integration hardening. Each slice delivers executable behavior against feature 006's ports without redefining them.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| 1 | Adapter skeleton and persistence root | US-1, US-3 | M | — | false | HITL | Establishes default adapter boundary and path/open-mode rules behind feature 006 ports. |
| 2 | Repository isolation and schema metadata | US-1, US-2 | M | 1 | false | HITL | Encodes repository scope and schema-version governance that prevent drift. |
| 3 | Provenance and relationship validation | US-4, US-7 | M | 2 | true | HITL | Safety-critical false-edge mitigation and audit traceability. |
| 4 | Write-side port implementation | US-1, US-3, US-4 | L | 2, 3 | false | HITL | Implements approved graph mutations behind 006 contracts and must avoid partial writes. |
| 5 | Read snapshots and query DTOs | US-5 | L | 4 | false | HITL | MCP-facing read semantics cross a trust boundary and must remain mutation-free. |
| 6 | 006 conformance suite green | US-6 | M | 4, 5 | false | HITL | Required proof that this adapter satisfies the dependency feature's executable contract. |
| 7 | Drift diagnostics and final verification | US-2, US-7 | S | 6 | false | AFK | Additive diagnostics and existing-tool verification after contract behavior is implemented. |

## Slices

### Slice 1: Adapter skeleton and persistence root

**Scope:** Create the graph adapter package, configuration objects, persistence path derivation, and a minimal adapter that opens repository-partitioned storage under `var\graph` without exposing LlamaIndex objects.

**User Stories:** US-1, US-3

**Automation:** HITL

**Automation Reason:** Establishes default adapter boundary and local persistence assumptions that downstream features rely on.

**Deliverables:**

- `src\living_adr\graph\__init__.py` exports `LlamaIndexPropertyGraphAdapter`.
- `src\living_adr\graph\persistence.py` derives safe repository storage paths under `var\graph` and documents same-host/WAL assumptions.
- `src\living_adr\graph\llamaindex_adapter.py` initializes adapter internals behind 006 ports.
- `tests\graph\test_llamaindex_adapter_persistence.py` covers path derivation, reopen behavior, and no public LlamaIndex leakage.

**Checkpoint Criteria:**

- [ ] Repository storage paths are deterministic, collision-resistant, and stay under `var\graph`.
- [ ] Adapter can initialize and reopen a repository graph fixture.
- [ ] Public imports expose the adapter class but no LlamaIndex storage context or SQLite connection.

**Context Notes:**

- Key files: feature 006 `ports.py`, planned graph package, architecture `#tech-stack` and `#deployment`.
- Dependencies: feature 006 implemented first.
- Estimated complexity: Medium.

### Slice 2: Repository isolation and schema metadata

**Scope:** Store repository identity and graph schema version metadata per repository; reject missing/unsupported metadata and cross-repository node access.

**User Stories:** US-1, US-2

**Automation:** HITL

**Automation Reason:** Repository scope and schema version are high-impact correctness boundaries for graph trust.

**Deliverables:**

- `src\living_adr\graph\schema.py` with adapter schema constants, metadata DTOs, and migration result mapping.
- Adapter implementations for `current_schema_version` and `migrate_schema`.
- Tests for repository isolation, schema initialization, schema mismatch, and migration hook behavior.

**Checkpoint Criteria:**

- [ ] `current_schema_version(repository)` returns persisted metadata for initialized graphs.
- [ ] Missing/unsupported schema metadata fails deterministically or requires migration.
- [ ] Identical ADR/code-area identifiers in different repositories remain isolated.

**Context Notes:**

- Key files: `schema.py`, adapter, 006 graph models.
- Dependencies: Slice 1.
- Estimated complexity: Medium.

### Slice 3: Provenance and relationship validation

**Scope:** Define provenance records and validation that prevent unsupported entities/relationships from becoming authoritative graph edges.

**User Stories:** US-4, US-7

**Automation:** HITL

**Automation Reason:** This slice mitigates FM-08/FM-10 and determines whether graph answers are auditable.

**Deliverables:**

- `src\living_adr\graph\provenance.py` with provenance completeness checks.
- `src\living_adr\graph\llamaindex_mapping.py` mapping domain records/edges to validated internal property graph structures.
- Tests for missing provenance, unsupported relationship labels, repository mismatch, and extracted-edge quarantine/rejection.

**Checkpoint Criteria:**

- [ ] Every persisted node/edge requires ADR/evidence/decision/extraction provenance.
- [ ] Unsupported entity/relationship labels are rejected or quarantined before current graph persistence.
- [ ] Returned graph paths include provenance sufficient for ADR/evidence citation.

**Context Notes:**

- Key files: `provenance.py`, `llamaindex_mapping.py`, 006 `RelationshipType`, `GraphEdge`, `ADRPath`.
- Dependencies: Slice 2.
- Estimated complexity: Medium.

### Slice 4: Write-side port implementation

**Scope:** Implement `ArchitectureGraphStore` write methods for approved ADR projection, relationships, structural changes, supersession/retraction, schema migration, snapshot rebuild hook, and conformance report generation.

**User Stories:** US-1, US-3, US-4

**Automation:** HITL

**Automation Reason:** Write methods create authoritative graph projections and must honor approval, transaction, scope, and provenance constraints.

**Deliverables:**

- `LlamaIndexPropertyGraphAdapter` write methods matching 006 signatures.
- Transaction/rollback handling around multi-node/multi-edge updates where supported by backing persistence.
- Tests for ADR upsert, relationship add, structural change record, supersede/retract, reopen after write, and partial-write failure behavior.

**Checkpoint Criteria:**

- [ ] All write methods accept 006 `RepositoryIdentity` and `ApprovedReviewDecision` without signature changes.
- [ ] Write failures do not expose partially current projections.
- [ ] Persisted graph can be reopened with nodes/edges/provenance intact.

**Context Notes:**

- Key files: adapter, mapping, persistence, schema, provenance, conformance helper.
- Dependencies: Slices 2 and 3.
- Estimated complexity: High.

### Slice 5: Read snapshots and query DTOs

**Scope:** Implement `ArchitectureContextQuery` read methods and `GraphSnapshotRef` handling for MCP-safe context delivery.

**User Stories:** US-5

**Automation:** HITL

**Automation Reason:** MCP read behavior crosses the IDE/assistant trust boundary and must expose citations without write authority.

**Deliverables:**

- `src\living_adr\graph\snapshots.py` with snapshot refs/currentness checks.
- Adapter read methods: `traverse_from_code_area`, `answer_why`, `fetch_adr`, `list_adrs`, `validate_snapshot_current`.
- Tests for read-only behavior, snapshot current/stale handling, bounded results, citations, and no backend object leakage.

**Checkpoint Criteria:**

- [ ] MCP-facing methods return only 006 domain DTOs.
- [ ] Read methods require repository scope and do not mutate graph state.
- [ ] Snapshot validation returns deterministic current/stale results.

**Context Notes:**

- Key files: `snapshots.py`, adapter query methods, 006 query DTOs.
- Dependencies: Slice 4.
- Estimated complexity: High.

### Slice 6: 006 conformance suite green

**Scope:** Wire the LlamaIndex adapter into feature 006's conformance suite and make the full suite pass.

**User Stories:** US-6

**Automation:** HITL

**Automation Reason:** Passing conformance is the feature's core contract and may reveal architectural contract mismatches requiring careful review.

**Deliverables:**

- `tests\graph\test_llamaindex_adapter_conformance.py` adapter factory and suite invocation.
- Any adapter fixes required by repository-scope, approval, read/write separation, schema, snapshot, and no-leak conformance failures.
- Documentation comments for future adapter owners showing how to run the same suite.

**Checkpoint Criteria:**

- [ ] Feature 006 conformance suite passes against `LlamaIndexPropertyGraphAdapter`.
- [ ] No conformance test is weakened, skipped, or redefined to fit LlamaIndex.
- [ ] Adapter direct tests and conformance tests agree on repository scope and provenance behavior.

**Context Notes:**

- Key files: `tests\conformance\graph_store_conformance.py`, `tests\graph\test_llamaindex_adapter_conformance.py`, adapter.
- Dependencies: Slices 4 and 5.
- Estimated complexity: Medium.

### Slice 7: Drift diagnostics and final verification

**Scope:** Add drift/false-edge diagnostics, import-boundary checks, package exports, and final project verification.

**User Stories:** US-2, US-7

**Automation:** AFK

**Automation Reason:** Additive validation and existing-tool verification after HITL-reviewed adapter behavior is complete.

**Deliverables:**

- `tests\graph\test_llamaindex_adapter_validation.py` final drift diagnostics coverage if not completed earlier.
- Import-boundary checks that graph adapter is the only LlamaIndex-dependent package and core remains clean.
- `uv run pytest` and `uv run ruff check` verification.

**Checkpoint Criteria:**

- [ ] `check_conformance(repository)` reports missing provenance, schema mismatch, orphan edges, and repository mismatch.
- [ ] Core ports remain free of LlamaIndex imports; LlamaIndex imports stay in adapter package.
- [ ] Existing pytest and Ruff commands pass.

**Context Notes:**

- Key files: adapter validation tests, package exports, import-boundary tests, `pyproject.toml` commands.
- Dependencies: Slice 6.
- Estimated complexity: Low.

## Slice Dependency Graph

```text
Slice 1 ──→ Slice 2 ──→ Slice 4 ──→ Slice 5 ──→ Slice 6 ──→ Slice 7
              └──→ Slice 3 ─────────┘
```

## Slice Dependency Graph (Machine-Readable)

```yaml
slices:
  - id: 1
    name: Adapter skeleton and persistence root
    depends_on: []
    parallelizable: false
    automation: HITL
    automation_reason: "Establishes default adapter boundary and path/open-mode rules behind feature 006 ports."
    checkpoint_criteria_count: 3
  - id: 2
    name: Repository isolation and schema metadata
    depends_on: [1]
    parallelizable: false
    automation: HITL
    automation_reason: "Encodes repository scope and schema-version governance that prevent drift."
    checkpoint_criteria_count: 3
  - id: 3
    name: Provenance and relationship validation
    depends_on: [2]
    parallelizable: true
    automation: HITL
    automation_reason: "Safety-critical false-edge mitigation and audit traceability."
    checkpoint_criteria_count: 3
  - id: 4
    name: Write-side port implementation
    depends_on: [2, 3]
    parallelizable: false
    automation: HITL
    automation_reason: "Implements approved graph mutations behind 006 contracts and must avoid partial writes."
    checkpoint_criteria_count: 3
  - id: 5
    name: Read snapshots and query DTOs
    depends_on: [4]
    parallelizable: false
    automation: HITL
    automation_reason: "MCP-facing read semantics cross a trust boundary and must remain mutation-free."
    checkpoint_criteria_count: 3
  - id: 6
    name: 006 conformance suite green
    depends_on: [4, 5]
    parallelizable: false
    automation: HITL
    automation_reason: "Required proof that this adapter satisfies the dependency feature's executable contract."
    checkpoint_criteria_count: 3
  - id: 7
    name: Drift diagnostics and final verification
    depends_on: [6]
    parallelizable: false
    automation: AFK
    automation_reason: "Additive diagnostics and existing-tool verification after contract behavior is implemented."
    checkpoint_criteria_count: 3
```

> **Note:** `parallelizable` is a static planning-time hint, not a runtime guarantee. `crispy-implement` re-evaluates parallelizability dynamically based on dependency satisfaction and file-set conflict detection at execution time.

## Context Management

- Maximum files open per slice: 6 implementation files plus related tests.
- Recommended context window reset points: after Slice 2, after Slice 4, and before Slice 6 conformance work.
- State that must carry across slices: do not modify 006 ports; repository scope is mandatory; graph data is projection not authority; provenance is required on every entity/edge; workflow is the single writer; MCP is read-only.

## Verification Strategy

The complete feature is verified by targeted adapter tests, feature 006 conformance suite execution against the LlamaIndex adapter fixture, repository isolation and reopen tests, provenance/schema drift diagnostics, read snapshot/query tests, import-boundary checks, `uv run pytest`, and `uv run ruff check`.