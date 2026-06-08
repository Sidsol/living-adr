# Research: mcp-context-server

## Research Basis

Read in full before planning:

- `..\..\vision.md`
- `..\..\domain-research.md`
- `..\..\architecture.md`
- `..\..\feature-map.md`
- `..\..\roadmap.md`
- `..\002-tracked-repository-configuration\spec.md`
- `..\002-tracked-repository-configuration\intent.md`
- `..\007-llamaindex-property-graph-adapter\spec.md`
- `..\007-llamaindex-property-graph-adapter\intent.md`

## Feature Brief Extract

Feature 012 `mcp-context-server` is P1, estimated at 6 slices, parallelizable, and depends on features 007 and 002. It implements the read-only MCP context server using the official Python MCP SDK, `ArchitectureContextQuery`, repository scoping, stdio transport, minimal local trust assumptions, and tools/resources for `answer_why`, `fetch_adr`, and `list_adrs` with citations to approved ADRs. It excludes writes, SCM credentials, and broad IDE UX.

## Domain Findings Relevant to This Feature

- MCP is a host/client/server protocol for tools, resources, and prompts over transports including stdio and Streamable HTTP. For PoC, stdio best matches local IDE/assistant integration and avoids premature HTTP/OAuth decisions.
- MCP local servers carry trust risk because hosts execute local processes. LivingADR mitigates this by making the server small, read-only, and credential-isolated.
- Architecture why-answers are valuable only when they cite approved ADR context. GraphRAG/PropertyGraph retrieval improves multi-hop context but can produce false edges; the MCP server must surface provenance and avoid unsupported claims.
- Observability traces can leak sensitive content. Feature 012 should emit metadata summaries only and leave LangSmith implementation to feature 013.

## Inherited Architecture Constraints

- `mcp-context-server` is a separate deployable from `workflow-service` (`..\..\architecture.md#service-boundaries`).
- The server depends only on `ArchitectureContextQuery`, not mutation services, webhook handlers, GitHub credentials, or write-side graph ports.
- Graph queries are repository-scoped by `RepositoryIdentity` and return DTOs such as `WhyAnswer`, `ProvenancedADR`, and `ADRRef` (`..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`).
- PoC deployment uses two local processes sharing same-host persistence; workflow is the only writer and MCP opens read-only (`..\..\architecture.md#deployment`).
- Cross-cutting security requires untrusted input handling, prompt/tool-injection resistance, and read-only MCP exposure (`..\..\architecture.md#cross-cutting`).

## Dependency Contract Findings

### Feature 002

Feature 002 provides:

- `RepositoryIdentity`, `RepositoryConfig`, `LivingADRConfig`, config loading, and startup diagnostics.
- Restart-required config semantics; no hot reload.
- A thin `Observability` port with `record_event`, `increment_counter`, and `start_span` plus a no-op implementation.
- Default-deny guidance for raw prompts, diffs, drafts, reviewer comments, secrets, and retrieved context.

Feature 012 must bind to these contracts and must not define another repository model, config loader, or observability abstraction.

### Feature 007 / 006

Feature 007 implements the default LlamaIndex adapter behind feature 006's graph ports. For MCP, the relevant inherited surface is `ArchitectureContextQuery`:

- `traverse_from_code_area(...) -> list[ADRPath]`
- `answer_why(...) -> WhyAnswer`
- `fetch_adr(...) -> ProvenancedADR`
- `list_adrs(...) -> list[ADRRef]`
- `validate_snapshot_current(...) -> bool`

Feature 012 must query through this read-side port only, never through LlamaIndex APIs or write-side graph stores.

## Risks Carried Forward

| Risk | Source | Planning Response |
|---|---|---|
| MCP local-server trust failure | FM-15 | Keep server read-only, document capabilities, inject no write services or SCM credentials. |
| MCP auth mismatch | FM-16 | Use stdio/local process trust for PoC; defer HTTP/OAuth. |
| Low answer faithfulness | FM-11 | Return citations/provenance and explicit no-context responses. |
| Retriever misses context | FM-12 | Respect `ArchitectureContextQuery` results and record metadata for later feature 013 evaluation. |
| Graph false edges | FM-10 / feature 007 | Surface provenance; do not create or repair graph edges in MCP. |
| Sensitive trace leakage | FM-21 / feature 002 | Observability metadata only. |
| Swappable-port erosion | architecture | Depend on `ArchitectureContextQuery` DTOs, not LlamaIndex internals. |

## Codebase State Assumption

LivingADR is planned as a greenfield implementation under `C:\repos\living-adr`; this feature-level planning does not inspect or change production code. The file-level plan names future modules based on `..\..\architecture.md#repositories` and dependency feature plans.

## Research Conclusions

1. The MCP context server should be a thin adapter from MCP request/response conventions to existing LivingADR read-side domain ports.
2. Read-only behavior is the central quality gate, not an implementation detail.
3. Repository scoping, safe serialization, bounded validation, and citation preservation are the main feature-specific responsibilities.
4. Transport/auth scope is intentionally narrow: stdio/local PoC only.
5. Observability must be metadata-only and should bind to feature 002's port so feature 013 can upgrade implementation later.
