# Codebase Research: LivingADR walking skeleton

> **Scope note:** The target implementation repository `C:\repos\living-adr` does not exist yet in the current workspace. This research is therefore grounded in the authoritative greenfield architecture and domain research artifacts, plus a read-only filesystem check confirming no implementation code is present. No production code was read or modified.

## Architecture Overview
LivingADR is planned as one Python 3.12 repo named `living-adr` with shared internal packages and two deployables: `workflow-service` and `mcp-context-server`. The selected architecture is a hybrid single repo / two deployables topology. The `workflow-service` owns event intake, workflow orchestration, HITL review state, audit, and approved graph mutation; the `mcp-context-server` owns read-only IDE/assistant context delivery.

The core safety seam is approval-bound mutation. `ApprovalBoundMutationService` is the only component allowed to call write-side `ArchitectureGraphStore` methods, and those writes require an `ApprovedReviewDecision`. The read side uses `ArchitectureContextQuery` and must not depend on mutation services, webhook handlers, GitHub credentials, or write-side graph ports.

Relevant authoritative anchors:
- `..\..\architecture.md#tech-stack`: Python 3.12, FastAPI, LangGraph, LlamaIndex behind ports, MCP SDK, SQLite/WAL, pytest, Ruff, uv.
- `..\..\architecture.md#service-boundaries`: workflow-service, mcp-context-server, core, scm, graph, approval-bound mutation boundary.
- `..\..\architecture.md#data-model`: `RepositoryIdentity`, `SCMEvent`, `StructuralChange`, `ChangeEvidence`, `ADRDraft`, `ApprovedReviewDecision`, `ADRRecord`, `ArchitectureGraph`, `AuditEvent`.
- `..\..\architecture.md#deployment`: local PoC uses two local processes sharing one filesystem and SQLite WAL; workflow is writer, MCP is read-only.
- `..\..\architecture.md#anti-patterns`: failure-mode inverses to preserve in implementation.

## Directory Structure
Planned repo layout from architecture:

```text
C:\repos\living-adr\
  pyproject.toml
  uv.lock
  src\living_adr\
    apps\workflow_service\
    apps\mcp_context_server\
    core\
    scm\
    graph\
    workflow\
    hitl\
    observability\
  tests\
  var\.gitkeep
```

No implementation files currently exist under `C:\repos\living-adr`, so the walking skeleton will likely create initial files in these planned areas.

## Logic Flows

### Flow: Planned approved mutation path
1. Entry point: `workflow-service` receives or replays merged PR event.
2. Event normalized to `SCMEvent` with `RepositoryIdentity` scope.
3. Workflow emits `StructuralChange` and immutable `ChangeEvidence`.
4. Drafting creates provisional `ADRDraft`; not authoritative.
5. HITL approval mints `ApprovedReviewDecision` only for approve/approve-after-edit.
6. `ApprovalBoundMutationService` validates decision, draft content hash, repository scope, and one-shot semantics.
7. Write-side `ArchitectureGraphStore` persists an `ADRRecord` projection and audit linkage.
8. `mcp-context-server` reads through `ArchitectureContextQuery` only.

### Flow: Planned MCP why query path
1. Entry point: MCP host calls a read-only `answer_why`-style tool/resource.
2. `mcp-context-server` passes repository scope and optional code area to `ArchitectureContextQuery`.
3. Query returns `WhyAnswer` with ranked ADR references, graph paths, and citations.
4. MCP response cites approved ADR/context only; it must not expose pending drafts or raw unapproved PR evidence as authoritative rationale.

## Data Models

### Model: RepositoryIdentity
- Source: `..\..\architecture.md#data-model`.
- Fields: host, owner, repo, opaque provider repo id.
- Relationships: scopes every domain record, graph node, SCM call, and MCP query.

### Model: SCMEvent
- Source: `..\..\architecture.md#data-model`.
- Fields: repository, provider delivery identity, timestamps, fetch handles.
- Relationships: source event for structural changes and replay/idempotency.

### Model: StructuralChange / ChangeEvidence
- Source: `..\..\architecture.md#data-model`.
- Fields: repository, architecture-significant change class, PR evidence, diff summaries, source citations.
- Relationships: `StructuralChange` later links to approved ADR node; evidence remains separate from inferred rationale.

### Model: ADRDraft
- Source: `..\..\architecture.md#data-model`.
- Fields: repository, provisional ADR content/classification output.
- Relationships: never authoritative until approved by HITL.

### Model: ApprovedReviewDecision
- Source: `..\..\architecture.md#data-model` and service-boundaries capability semantics.
- Fields: decision id, reviewer id, minted timestamp, TTL, consumed timestamp, draft id, draft content hash, structural change event id, decision version, target mutation fingerprint.
- Relationships: required capability for authoritative mutation; rejected/deferred decisions cannot authorize writes.

### Model: ADRRecord
- Source: `..\..\architecture.md#data-model`.
- Fields: repository, human-readable Markdown ADR, structured metadata/projection.
- Relationships: canonical approved decision record; graph is a queryable projection.

## Integration Points

| Integration | Type | Location | Notes |
|---|---|---|---|
| GitHub App / webhooks | External SCM | Planned `src\living_adr\scm\` and `apps\workflow_service` | Production integration deferred; walking skeleton should use fixture/replay. |
| Claude / Anthropic | External LLM | Planned adapter behind `ClaudeClient` | Must not be called by this feature; deterministic stub only. |
| LangGraph | Workflow runtime | Planned `src\living_adr\workflow\` | Full durable checkpointing deferred; skeleton may use port-shaped sequential flow. |
| LlamaIndex PropertyGraphIndex | Graph adapter | Planned `src\living_adr\graph\` | Production adapter deferred; skeleton should use a stub graph/query store behind port-shaped interfaces. |
| MCP SDK stdio | IDE/assistant context | Planned `apps\mcp_context_server` | Walking skeleton may expose MCP-style callable function/CLI before full SDK conformance. |
| SQLite/WAL | Local persistence | Planned `var\` | Local stub persistence acceptable; workflow writer and MCP read-only behavior should be respected conceptually. |

## Configuration & Environment
- Architecture expects configuration/secrets through environment variables or `.env.local`; scaffold should create `.env.example`, not secrets.
- Tracked repositories are eventually first-class config in `living-adr.config.yaml`, but feature 001 can seed one hardcoded smoke fixture because repository configuration is feature 002.
- Local PoC deployment runs `living-adr-workflow` and `living-adr-mcp` from `C:\repos\living-adr`.

## Domain Failure Modes Relevant to This Skeleton
- FM-06 after-the-fact hallucinated rationale: stub draft must be labeled provisional/deterministic and cite fixture evidence.
- FM-08/FM-10 graph drift and false edges: stub graph should persist minimal provenance and avoid pretending to implement real graph extraction.
- FM-13 agent excessive agency: no model/tool output may mutate authoritative context directly.
- FM-15/FM-16 MCP trust/auth mismatch: skeleton MCP path must remain read-only and local.
- FM-17 webhook duplication/gaps/replay complexity: replay fixture should demonstrate idempotency at smoke depth.
- FM-20 HITL rubber-stamping: stub accept is for seam proof only; production meaningful review is deferred and must not be implied complete.
- FM-21 sensitive trace leakage: smoke tests should not export raw fixture/draft data externally.
- FM-23 docs-as-code without review gates: approved `ADRRecord` creation must remain behind the review decision.

## Technical Debt & Observations
- There is no implementation repository yet; initial implementation will combine scaffold work with feature code.
- Feature 001 intentionally precedes features 002, 003, 006, 007, 009, 010, 012, and 015, so it must use clearly named stubs rather than accidentally creating production contracts that later features are forced to preserve.
- The architecture requires `ApprovedReviewDecision` one-shot semantics, TTL, hash pinning, and audit linkage. Feature 001 should prove the shape and guard, but full durability belongs to feature 010.
- MCP SDK maturity risk is noted in architecture reviewer findings; feature 001 should keep the MCP-style surface thin and testable.

## Key Patterns
- Port-shaped boundaries: workflow and MCP depend on core interfaces, not concrete graph or SCM implementations.
- Repository scoping everywhere.
- Evidence/rationale separation: PR/diff facts are evidence; approved ADR records are rationale.
- Deterministic fakes for external systems in tests.
- Append-only/auditable mindset even when persistence is stubbed.
