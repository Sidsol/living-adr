# Implementation Outline: graph-store-ports-and-approval-seam

## Slice Strategy

The feature is split into six vertical slices matching the feature-map estimate. Foundational value objects come first, followed by the authoritative ADR record contract, then read/write ports, the approval-bound mutation facade, adapter conformance, and final package/integration verification. This ordering lets downstream features depend on stable contracts without waiting for a concrete LlamaIndex adapter.

## Slices Overview

| Slice | Name | Stories | Estimated Effort | Depends On | Parallelizable | Automation | Automation Reason |
|---|---|---|---|---|---|---|---|
| 1 | Core graph value objects | US-1 | M | — | false | HITL | Establishes stable graph vocabulary and repository-scope semantics consumed by every later slice. |
| 2 | ADR record repository and source hierarchy | US-2, US-6 | M | 1 | false | HITL | Defines authoritative-rationale semantics and must be reviewed against source-of-truth discipline. |
| 3 | Architecture graph read/write ports | US-3, US-6 | M | 1, 2 | false | HITL | Port signatures become cross-feature contracts for workflow, MCP, and adapters. |
| 4 | Approval-bound mutation service | US-4 | M | 2, 3 | false | HITL | Safety-critical boundary preventing unapproved authoritative mutations. |
| 5 | Adapter conformance suite | US-5 | M | 3, 4 | true | HITL | Future adapters must pass executable contract checks before becoming trusted persistence. |
| 6 | Integration exports and verification | US-6 | S | 1, 2, 3, 4, 5 | false | AFK | Additive import/export and verification tasks once contracts are established. |

## Slices

### Slice 1: Core graph value objects

**Scope:** Define typed, repository-scoped graph and query result value objects.

**User Stories:** US-1

**Automation:** HITL

**Automation Reason:** Establishes shared vocabulary and validation semantics that become hard to change after adapters land.

**Deliverables:**

- `src\living_adr\core\graph\models.py` with graph IDs, relationship labels, edges, snapshots, schema versions, conformance reports, and query result DTOs.
- `tests\core\graph\test_graph_models.py` covering valid/invalid value construction and repository scope.

**Checkpoint Criteria:**

- [ ] Every graph value crossing a port carries or references `RepositoryIdentity` where needed.
- [ ] Unsupported relationship labels fail deterministically.
- [ ] Query result DTOs expose ADR citations/provenance, not backend objects.

**Context Notes:**

- Key files: feature 002 `RepositoryIdentity`, new graph models/tests.
- Dependencies: feature 002 core repository identity contract.
- Estimated complexity: Medium.

### Slice 2: ADR record repository and source hierarchy

**Scope:** Define authoritative `ADRRecord` and `ADRRecordRepository` expectations, including status, provenance, approved decision linkage, and projection conflict handling.

**User Stories:** US-2, US-6

**Automation:** HITL

**Automation Reason:** This slice encodes the architecture's source-of-truth hierarchy and prevents graph projections from becoming unreviewed rationale.

**Deliverables:**

- `src\living_adr\core\adr.py` with `ADRRecord`, `ADRStatus`, `ADRRecordRepository`, and source hierarchy documentation.
- `tests\core\test_adr_records.py` covering approved-decision linkage, repository scope, and projection conflict expectations.

**Checkpoint Criteria:**

- [ ] `ADRRecord` cannot be valid without repository identity and approved decision linkage.
- [ ] Repository contract states ADR records are canonical approved rationale.
- [ ] Projection conflict behavior is explicit: rebuild/flag, never silent overwrite.

**Context Notes:**

- Key files: ADR core module, graph models, feature 010 future approval durability notes.
- Dependencies: Slice 1.
- Estimated complexity: Medium.

### Slice 3: Architecture graph read/write ports

**Scope:** Define `ArchitectureGraphStore` and `ArchitectureContextQuery` Protocols using only LivingADR domain value objects.

**User Stories:** US-3, US-6

**Automation:** HITL

**Automation Reason:** These signatures are the swap seam consumed by workflow, MCP, and graph adapters.

**Deliverables:**

- `src\living_adr\core\graph\ports.py` with write/read protocols matching `..\..\architecture.md#service-boundaries`.
- `tests\core\graph\test_graph_ports.py` verifying mutation signatures require approval and query signatures are read-only.

**Checkpoint Criteria:**

- [ ] Every write method requires `RepositoryIdentity` and `ApprovedReviewDecision`.
- [ ] Every read method requires `RepositoryIdentity` and exposes no write capability.
- [ ] Port modules import no LlamaIndex, LangSmith, FastAPI, MCP, or DB-specific types.

**Context Notes:**

- Key files: graph ports, graph models, ADR model, approval model.
- Dependencies: Slices 1 and 2.
- Estimated complexity: Medium.

### Slice 4: Approval-bound mutation service

**Scope:** Define the only workflow-facing write facade and reject invalid approval before adapter calls.

**User Stories:** US-4

**Automation:** HITL

**Automation Reason:** Safety-critical mutation boundary and SM-05 prerequisite.

**Deliverables:**

- `src\living_adr\core\approval.py` with `ApprovedReviewDecision` contract and validation errors.
- `src\living_adr\core\graph\approval_bound_mutation.py` with mutation request DTOs and service methods.
- `tests\core\graph\test_approval_bound_mutation.py` proving invalid approvals make zero adapter calls.

**Checkpoint Criteria:**

- [ ] `None`, rejected, repository-mismatched, hash-mismatched, and target-mismatched decisions raise before adapter calls.
- [ ] Valid approved decisions delegate exactly once to the write port.
- [ ] Observability calls are metadata-only and use feature 002 `Observability` seam.

**Context Notes:**

- Key files: approval model, mutation service, fake graph store test double.
- Dependencies: Slices 2 and 3.
- Estimated complexity: Medium.

### Slice 5: Adapter conformance suite

**Scope:** Provide reusable tests and fake adapter fixture that future graph adapters must satisfy.

**User Stories:** US-5

**Automation:** HITL

**Automation Reason:** Conformance suite defines trust criteria for future persistence and retrieval adapters.

**Deliverables:**

- `tests\conformance\graph_store_conformance.py` reusable test mixin/helpers.
- `tests\fakes\in_memory_graph_store.py` fake adapter implementing the port for conformance validation.
- `tests\conformance\test_in_memory_graph_conformance.py` proving the suite executes.

**Checkpoint Criteria:**

- [ ] Suite fails adapters that ignore repository scoping.
- [ ] Suite fails adapters that allow mutation without approval.
- [ ] Suite fails adapters that return concrete persistence objects through domain ports.
- [ ] Future adapter opt-in instructions are included in test helper docstrings or README comments.

**Context Notes:**

- Key files: conformance helpers, fake adapter, graph ports/service tests.
- Dependencies: Slices 3 and 4.
- Estimated complexity: Medium.

### Slice 6: Integration exports and verification

**Scope:** Export contracts consistently and verify boundary constraints.

**User Stories:** US-6

**Automation:** AFK

**Automation Reason:** Pure verification/export work after human-reviewed contract slices are complete.

**Deliverables:**

- `src\living_adr\core\graph\__init__.py` and `src\living_adr\core\__init__.py` exports if package conventions use exports.
- Import-boundary tests or static checks for forbidden concrete dependencies.
- Full pytest and Ruff verification.

**Checkpoint Criteria:**

- [ ] Downstream modules can import graph/ADR/approval contracts from stable package paths.
- [ ] Forbidden concrete dependencies do not appear in core graph/approval modules.
- [ ] Existing pytest and Ruff commands pass.

**Context Notes:**

- Key files: package exports, import-boundary tests, `pyproject.toml` commands.
- Dependencies: all prior slices.
- Estimated complexity: Low.

## Slice Dependency Graph

```text
Slice 1 ──→ Slice 2 ──→ Slice 3 ──→ Slice 4 ──→ Slice 5 ──→ Slice 6
   └──────────────→ Slice 3
```

## Slice Dependency Graph (Machine-Readable)

```yaml
slices:
  - id: 1
    name: Core graph value objects
    depends_on: []
    parallelizable: false
    automation: HITL
    automation_reason: "Establishes stable graph vocabulary and repository-scope semantics consumed by every later slice."
    checkpoint_criteria_count: 3
  - id: 2
    name: ADR record repository and source hierarchy
    depends_on: [1]
    parallelizable: false
    automation: HITL
    automation_reason: "Defines authoritative-rationale semantics and must be reviewed against source-of-truth discipline."
    checkpoint_criteria_count: 3
  - id: 3
    name: Architecture graph read/write ports
    depends_on: [1, 2]
    parallelizable: false
    automation: HITL
    automation_reason: "Port signatures become cross-feature contracts for workflow, MCP, and adapters."
    checkpoint_criteria_count: 3
  - id: 4
    name: Approval-bound mutation service
    depends_on: [2, 3]
    parallelizable: false
    automation: HITL
    automation_reason: "Safety-critical boundary preventing unapproved authoritative mutations."
    checkpoint_criteria_count: 3
  - id: 5
    name: Adapter conformance suite
    depends_on: [3, 4]
    parallelizable: true
    automation: HITL
    automation_reason: "Future adapters must pass executable contract checks before becoming trusted persistence."
    checkpoint_criteria_count: 4
  - id: 6
    name: Integration exports and verification
    depends_on: [1, 2, 3, 4, 5]
    parallelizable: false
    automation: AFK
    automation_reason: "Additive import/export and verification tasks once contracts are established."
    checkpoint_criteria_count: 3
```

> **Note:** `parallelizable` is a static planning-time hint, not a runtime guarantee. `crispy-implement` re-evaluates parallelizability dynamically based on dependency satisfaction and file-set conflict detection at execution time.

## Context Management

- Maximum files open per slice: 5 implementation files plus related tests.
- Recommended context window reset points: after Slice 2, after Slice 4, and before final verification.
- State that must carry across slices: repository scope is mandatory; approved ADR records are authoritative; graph data is projection; mutation service is the only workflow write facade; feature 010 owns durable capability consumption.

## Verification Strategy

Run existing project checks after implementation: `uv run pytest` and `uv run ruff check`. Add targeted checks that invalid approval attempts make zero adapter calls, MCP/read ports expose no mutation methods, conformance suite executes against the fake adapter, and core graph/approval modules import no concrete persistence or runtime dependencies.
