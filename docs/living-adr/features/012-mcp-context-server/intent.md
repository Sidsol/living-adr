# Architecture Intent: mcp-context-server

## Current State

LivingADR architecture selects a hybrid single repo with two deployables: `workflow-service` for ingestion/HITL/mutations and `mcp-context-server` for read-only context delivery (`..\..\architecture.md#service-boundaries`, `..\..\architecture.md#repositories`, `..\..\architecture.md#deployment`). Feature 002 supplies repository configuration and the `Observability` port. Feature 007 supplies the default graph adapter behind the stable `ArchitectureContextQuery` read-side port.

No production implementation is written in this planning phase.

## Desired State

After this feature, `living-adr-mcp` starts a stdio MCP server that exposes approved architecture context through `answer_why`, `fetch_adr`, and `list_adrs`. It loads repository config through feature 002, queries only through `ArchitectureContextQuery`, serializes citation-bearing DTOs, emits metadata-only observability, and cannot mutate graph state, publish ADRs, call SCM APIs, invoke Claude, or approve decisions.

## Architecture Anchors

- `..\..\architecture.md#tech-stack` — official Python `mcp` SDK, Python 3.12, pytest/Ruff, stdio transport.
- `..\..\architecture.md#service-boundaries` — separate MCP context server and strict dependency on `ArchitectureContextQuery` only.
- `..\..\architecture.md#data-model` — `RepositoryIdentity`, `ADRRef`, `WhyAnswer`, `ProvenancedADR`, `QuerySession` / `RetrievalTrace` concepts.
- `..\..\architecture.md#cross-cutting` — read-only MCP, safe observability, prompt/tool-injection mitigation, source-of-truth discipline.
- `..\..\architecture.md#anti-patterns` — FM-11, FM-12, FM-15, FM-16, FM-21, and port-swappability failures.
- `..\..\architecture.md#deployment` — local two-process PoC, same-host WAL/read-only MCP access.
- `..\..\architecture.md#repositories` — single `living-adr` repo, app path under `src\living_adr\apps\mcp_context_server`.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| MCP app | Architecture selected SDK/stdio | App bootstrap and entrypoint plan | Add MCP server module and startup tests |
| Config | Feature 002 contract | MCP uses shared config and repo identity | Wire config loader into app construction |
| Graph reads | Feature 007 query port | MCP tools call `ArchitectureContextQuery` only | Add handler layer and fake query tests |
| Serialization | Domain DTOs planned | Stable JSON-like responses with citations | Add response mappers |
| Safety | Read-only boundary required | No write services imported/injected | Add dependency and capability tests |
| Observability | Feature 002 no-op port | Metadata-only MCP summaries | Add wrapper calls and tests |
| Docs | Local stdio transport chosen | Host config guidance with no secrets | Add operator docs or README section |

## Options Considered

### Option A: In-process MCP inside workflow-service

**Approach:** Add MCP tools to the workflow service process and reuse its graph/store dependencies.

- Pros: Fewer processes, simpler local startup.
- Cons: Collapses trust boundaries, risks exposing mutation services/SCM credentials to the MCP surface, conflicts with architecture-selected two deployables.
- Effort: Low.
- Risk: High.

### Option B: Standalone read-only stdio MCP adapter over `ArchitectureContextQuery` (selected)

**Approach:** Build a separate `living-adr-mcp` process using the Python MCP SDK over stdio. Inject only config, `ArchitectureContextQuery`, and `Observability`; register read-only tools/resources.

- Pros: Matches architecture, preserves graph-port swappability, minimizes MCP trust blast radius, keeps PoC auth simple, directly supports IDE/assistant use.
- Cons: Requires a second process and careful local configuration docs.
- Effort: Medium.
- Risk: Low-to-Medium.

### Option C: Remote HTTP/Streamable HTTP MCP service

**Approach:** Host MCP remotely with HTTP transport and authorization.

- Pros: Better for shared/team deployment and enterprise policy.
- Cons: Premature for PoC, reopens OAuth/identity questions, complicates local single-user validation, not needed for stdio client integration.
- Effort: High.
- Risk: Medium-to-High.

### Option D: Direct graph/LlamaIndex access from MCP tools

**Approach:** Let MCP handlers instantiate the LlamaIndex adapter or query graph internals directly.

- Pros: Potentially faster to prototype specific queries.
- Cons: Violates the swappable-port philosophy, bypasses feature 007/006 contracts, risks write-handle leakage, and makes future graph replacement harder.
- Effort: Low now, high later.
- Risk: High.

## Selected Approach

Select **Option B: Standalone read-only stdio MCP adapter over `ArchitectureContextQuery`**.

Rationale: Feature 012 exists to isolate the IDE/assistant trust boundary from the workflow mutation boundary. A thin MCP adapter over the read-side port delivers the MVP context surface while honoring source-of-truth and swappable-storage constraints. It also lets feature 013 later observe query quality without coupling MCP to LangSmith directly.

## Anti-Patterns to Avoid

- Redefining `ArchitectureContextQuery`, `RepositoryIdentity`, `ADRRef`, `WhyAnswer`, or `ProvenancedADR` in MCP code.
- Importing or injecting `ArchitectureGraphStore`, `ApprovalBoundMutationService`, GitHub providers, Claude clients, HITL services, or write credentials.
- Exposing MCP tools named or shaped like `approve`, `edit`, `reject`, `publish`, `upsert`, `migrate`, `rebuild`, `supersede`, or `retract`.
- Returning LlamaIndex objects, storage contexts, raw SQLite handles, filesystem internals, or raw stack traces.
- Treating graph answers as authoritative when they lack approved ADR citations.
- Logging raw ADR content, prompts, retrieved context, graph paths, secrets, or full errors through observability.
- Adding HTTP/OAuth or remote hosting into the PoC stdio feature.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add MCP app modules, handler/serialization layer, startup wiring, tests, and local stdio configuration documentation under the single Python repo. | High |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| MCP SDK API maturity changes | Medium | Medium | Wrap SDK usage in small app module; test registration behavior; keep domain handlers SDK-light. |
| Accidental write dependency imported | Medium | High | Constructor accepts only query/config/observability; add tests/static import checks for forbidden dependencies. |
| Cross-repository data leakage | Medium | High | Resolve repository key through `LivingADRConfig`; query with explicit `RepositoryIdentity`; test same-id ADRs across repos. |
| Answers overstate unsupported rationale | Medium | High | Preserve `WhyAnswer` citations and explicit no-context responses; do not synthesize new rationale in MCP. |
| Read sees partial graph write | Medium | Medium | Use feature 007 snapshot/current validation, retryable stale/busy errors, and no write handles. |
| Sensitive telemetry leakage | Medium | High | Metadata whitelist only; feature 013 owns raw-export controls. |
| Local user misconfigures server with secrets | Low | Medium | Documentation shows no secrets in MCP host config; credentials remain with workflow/env as applicable. |

## Design Commitments

- The server is **read-only by construction**.
- The server is **stdio-only for PoC**.
- The server is a **protocol adapter**, not a retrieval engine.
- All graph context access flows through **feature 007/006 `ArchitectureContextQuery`**.
- All repository scoping and config validation flows through **feature 002**.
- Observability uses the **feature 002 `Observability` port** without redefining telemetry abstractions.
