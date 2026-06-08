# Architecture Intent: graph-store-ports-and-approval-seam

## Current State

LivingADR is scaffold-only in `C:\repos\living-adr`; no graph, ADR repository, approval, or adapter modules exist. Planning documents already define the target seam: `core` owns `ArchitectureGraphStore`, `ArchitectureContextQuery`, `ADRRecordRepository`, `ApprovedReviewDecision`, `RepositoryIdentity`, and `Observability`; implementations live behind adapters (`..\..\architecture.md#service-boundaries`).

The architecture requires repository scope on graph/SCM/MCP methods, a single workflow writer with read-only MCP access, and a hard boundary where graph mutations are impossible without `ApprovedReviewDecision` (`..\..\architecture.md#service-boundaries`). The data model defines `ADRRecord` as canonical approved rationale and `ArchitectureGraph` as a versioned projection (`..\..\architecture.md#data-model`). Cross-cutting rules require transactional approval-bound graph mutation, audit linkage, graph governance, default-deny observability payloads, and source-of-truth discipline (`..\..\architecture.md#cross-cutting`). Anti-patterns FM-06, FM-08, FM-10, FM-13, FM-15, and FM-23 warn against hallucinated rationale, graph drift, false edges, excessive agency, MCP mutation power, and docs without review gates (`..\..\architecture.md#anti-patterns`).

Feature 002 is the dependency source for `RepositoryIdentity`, `RepositoryConfig`, and the thin `Observability` port. Feature 006 must consume those seams rather than redefining repository configuration or LangSmith integration.

## Desired State

After this feature, downstream code can import stable domain ports and value objects from core. Workflows can request approved graph mutations through `ApprovalBoundMutationService`; MCP can query through `ArchitectureContextQuery`; future graph adapters can run a reusable conformance suite. No caller sees LlamaIndex-specific types, database handles, or concrete persistence details through the port.

The source-of-truth hierarchy is explicit and testable:

1. Code/PR data and `ChangeEvidence` are evidence.
2. Approved `ADRRecord` objects are authoritative rationale.
3. Graph nodes/edges are projections with citations and schema-version metadata.
4. Conflicts between projections and ADR records are surfaced as rebuild/conformance failures, not silently overwritten.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Graph value objects | No implementation | Typed repository-scoped graph/domain values | Create core graph model module and tests |
| ADR records | Planned only | `ADRRecord` and repository expectations make approved ADRs authoritative | Define model/protocol and source hierarchy |
| Write port | Planned sketch | `ArchitectureGraphStore` Protocol with approval on every mutation | Create port surface and signature tests |
| Read port | Planned sketch | `ArchitectureContextQuery` Protocol with read-only scoped methods | Create query port and no-write tests |
| Approval boundary | Planned architecture | `ApprovalBoundMutationService` rejects invalid approval before adapter calls | Create service contract, errors, and fake adapter tests |
| Adapter conformance | Required by architecture | Reusable tests future adapters must pass | Create conformance suite and fake adapter fixture |
| Dependency isolation | Concrete deps in pyproject | Core port modules import no LlamaIndex/LangSmith/FastAPI/MCP | Add import-boundary checks |

## Architecture Options

### Option A: Direct LlamaIndex-first adapter API

**Approach:** Implement the LlamaIndex adapter now and let workflows/MCP depend on its native API.

- ✅ Pros: Fast path to a working graph implementation; fewer abstract files initially.
- ❌ Cons: Violates the swap-seam requirement, blocks Neo4j/RDF adapters, leaks concrete persistence to MCP/workflow code, and increases graph schema drift risk.
- 🔧 Effort: Medium now, high later.

### Option B: Minimal loose Python protocols only

**Approach:** Define very small `Protocol` interfaces with loosely typed dictionaries for nodes, edges, and answers.

- ✅ Pros: Low up-front code; easy for fake adapters.
- ❌ Cons: Allows stringly typed relationship labels, weak repository scoping, hidden LlamaIndex leakage, and incomplete conformance checks.
- 🔧 Effort: Low.

### Option C: Typed core ports plus approval-bound service and conformance suite (selected)

**Approach:** Define stable graph/ADR value objects, typed read/write ports, `ApprovalBoundMutationService`, specific errors, and reusable conformance tests using an in-memory fake adapter.

- ✅ Pros: Aligns with `..\..\architecture.md#service-boundaries`; makes mutation-impossible-without-approval testable; keeps graph implementation swappable; gives feature 007 an executable contract.
- ❌ Cons: More up-front contract design; relationship enum and query result shapes need careful review before adapters depend on them.
- 🔧 Effort: Medium.

## Selected Approach

**Option C: Typed core ports plus approval-bound service and conformance suite.**

Rationale: This feature is explicitly the high-leverage seam before feature 007. Typed contracts and conformance tests are the only option that satisfies the architecture's graph governance, source-of-truth discipline, repository-scope rule, and approval-bound mutation boundary while keeping workflow, HITL, MCP, and adapters decoupled.

## Module Surface Analysis

| Module | Inputs | Callers | Deletion test | Isolated-test candidate |
|---|---:|---|---|---|
| `src\living_adr\core\graph\models.py` | Field values, repository identity | ports, adapters, tests | Deleting forces dict/string graph values everywhere | Yes — pure value validation |
| `src\living_adr\core\adr.py` | ADR metadata/content, decision ids | workflow, graph service, publish-back | Deleting collapses authoritative rationale into graph internals | Yes — pure model/protocol tests |
| `src\living_adr\core\graph\ports.py` | Domain values | workflow, MCP, adapters | Deleting makes downstream depend on LlamaIndex | Yes — signature/import-boundary tests |
| `src\living_adr\core\approval.py` | review decision fields, hashes | HITL, mutation service, audit | Deleting weakens approval capability semantics | Yes — validation tests |
| `src\living_adr\core\graph\approval_bound_mutation.py` | mutation requests, approval, store, ADR repo, observability | workflow service | Deleting permits direct graph store writes | Yes — fake adapter/no-call tests |
| `tests\conformance\graph_store_conformance.py` | adapter factory | feature 007+ adapter tests | Deleting removes executable swap-seam contract | Yes — run with fake adapter |
| `tests\fakes\in_memory_graph_store.py` | domain values | conformance/service tests | Deleting makes conformance hard to validate before LlamaIndex | Yes — test helper |

## Anti-Patterns to Avoid

- **Concrete graph leakage:** exposing LlamaIndex nodes, retrievers, indices, sessions, or SQLite handles through core ports violates the swap seam.
- **Direct adapter writes:** letting workflow nodes call `ArchitectureGraphStore` directly bypasses the approval boundary and FM-13 mitigation.
- **Model output as authority:** Claude drafts or extracted graph edges must not become authoritative without approved `ADRRecord` linkage.
- **Graph as sole source of truth:** graph projections must cite ADR/evidence; `ADRRecord` remains canonical rationale.
- **Read-side mutation creep:** MCP-facing query modules must not import mutation service, SCM credentials, or write ports.
- **Stringly typed relationships:** unvalidated labels invite graph drift and false edges.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add core graph/ADR/approval contracts, approval-bound mutation service, conformance tests, fake adapter, import-boundary tests | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Port shape overfits LlamaIndex before adapter design | Medium | High | Use domain values only; conformance tests inspect for implementation leakage. |
| Approval semantics duplicate feature 010 durability | Medium | Medium | Limit this feature to validation shape and pre-adapter rejection; leave minting, one-shot consumption, TTL persistence, and audit durability to feature 010. |
| Relationship labels are too narrow | Medium | Medium | Define minimum enum plus explicit extension process in conformance tests. |
| Fake adapter passes while real adapter fails concurrency/provenance | Medium | Medium | Conformance suite focuses on semantic contract; feature 007 adds adapter-specific persistence/provenance tests. |
| Source hierarchy remains only comments | Low | High | Encode it in `ADRRecordRepository` expectations and conformance assertions. |
| Core ports accidentally import concrete deps | Medium | High | Add import-boundary tests/grep checks for LlamaIndex, LangSmith, FastAPI, MCP, and database imports. |
