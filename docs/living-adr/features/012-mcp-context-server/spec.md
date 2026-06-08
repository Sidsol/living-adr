# Feature Specification: mcp-context-server

## Overview

Feature 012 delivers the read-only `mcp-context-server` deployable for LivingADR. It uses the official Python MCP SDK over stdio to expose approved architecture decision context to IDEs and AI assistants through `ArchitectureContextQuery` from feature 007/006. The server offers `answer_why`, `fetch_adr`, and `list_adrs` surfaces with repository scoping, citations, bounded inputs, safe error handling, and no mutation capabilities.

This feature serves TH-05 Queryable Context Delivery and depends on feature 007 for the graph/query implementation and feature 002 for `RepositoryIdentity`, `RepositoryConfig`, startup config validation, and the `Observability` port.

## User Stories

### [US-1] Start a local read-only MCP server — Priority: P1
**As an** IDE or coding-agent user, **I want** a stdio MCP server process for LivingADR context, **so that** my tools can ask architecture questions without connecting to the workflow mutation surface.

#### Acceptance Scenarios
- **Given** a valid `living-adr.config.yaml`, **When** `living-adr-mcp` starts, **Then** it loads the config through feature 002 contracts and registers only read-only MCP capabilities.
- **Given** invalid repository configuration, **When** the MCP server starts, **Then** startup fails with feature 002 startup diagnostics before accepting MCP requests.
- **Given** the process is launched by an MCP host over stdio, **When** initialization completes, **Then** the host sees documented tools/resources for approved ADR context only.

### [US-2] List approved ADRs — Priority: P1
**As a** developer, **I want** to list ADRs for a configured repository, **so that** I can discover available architectural rationale.

#### Acceptance Scenarios
- **Given** approved ADRs exist in the graph for repository A, **When** `list_adrs` is called for repository A, **Then** the response returns scoped `ADRRef` data with id, title, status, and citation/provenance summaries.
- **Given** a status filter is provided, **When** `list_adrs` is called, **Then** the server passes the filter to `ArchitectureContextQuery.list_adrs` and maps unsupported statuses to a safe MCP error.
- **Given** repository B has ADRs with matching ids, **When** repository A is queried, **Then** no repository B ADRs appear.

### [US-3] Fetch one approved ADR with provenance — Priority: P1
**As a** developer or assistant, **I want** to fetch a specific ADR, **so that** I can inspect the authoritative rationale and its graph projection.

#### Acceptance Scenarios
- **Given** an ADR id exists for the repository, **When** `fetch_adr` is called, **Then** the response includes approved ADR content, metadata, status, provenance, and graph/citation details from `ProvenancedADR`.
- **Given** the ADR id is missing or outside repository scope, **When** `fetch_adr` is called, **Then** the server returns a not-found style MCP error without leaking other repository data.
- **Given** an optional snapshot is supplied, **When** `fetch_adr` is called, **Then** the query goes through `ArchitectureContextQuery.fetch_adr` using that snapshot without opening write handles.

### [US-4] Answer architecture why questions — Priority: P1
**As an** AI coding-assistant user, **I want** `answer_why` to answer architecture rationale questions with citations, **so that** assistant recommendations are grounded in approved ADR context.

#### Acceptance Scenarios
- **Given** a current graph snapshot with relevant ADRs, **When** `answer_why` receives a bounded question and optional code area, **Then** it returns a `WhyAnswer` containing cited ADRs, graph paths, confidence/relevance signals where available, and no unsupported claims.
- **Given** no approved context can answer the question, **When** `answer_why` is called, **Then** the response states that no approved ADR context was found rather than hallucinating rationale.
- **Given** an overlong question or excessive limit is requested, **When** validation runs, **Then** the server rejects or clamps the request according to documented limits before querying.

### [US-5] Preserve read-only and credential isolation — Priority: P1
**As a** platform owner, **I want** MCP context delivery isolated from mutation and SCM credentials, **so that** local MCP trust risks cannot alter authoritative architecture knowledge.

#### Acceptance Scenarios
- **Given** the MCP server is inspected or tested, **When** capabilities are enumerated, **Then** there are no approve, edit, reject, publish, graph-write, SCM-fetch, or config-mutation tools.
- **Given** implementation wiring is reviewed, **When** the MCP app is constructed, **Then** it receives only `ArchitectureContextQuery`, `LivingADRConfig`, and `Observability`, not `ArchitectureGraphStore`, `ApprovalBoundMutationService`, GitHub providers, Claude clients, or write credentials.
- **Given** a malicious prompt asks the assistant to mutate ADRs through MCP, **When** the host invokes available capabilities, **Then** no server-side mutation path exists.

### [US-6] Emit safe metadata observability — Priority: P2
**As a** maintainer, **I want** MCP access summaries and errors recorded through the feature 002 `Observability` port, **so that** later LangSmith instrumentation can measure retrieval use without leaking raw repository content.

#### Acceptance Scenarios
- **Given** any MCP tool succeeds or fails, **When** observability is enabled, **Then** the server records metadata-only events such as repository key, tool name, status, result count, latency bucket, and error type.
- **Given** ADR content, prompts, raw graph paths, or retrieved context are present in responses, **When** observability metadata is emitted, **Then** those raw payloads are excluded by default.

## Functional Requirements

- [FR-1] Provide the `living-adr-mcp` app/server plan under `src\living_adr\apps\mcp_context_server` using the official Python `mcp` SDK and stdio transport.
- [FR-2] Load and validate `LivingADRConfig` through feature 002 contracts; do not parse YAML directly inside MCP tool handlers.
- [FR-3] Resolve every request to a configured `RepositoryIdentity`; reject unknown repositories before calling the query port.
- [FR-4] Depend on `ArchitectureContextQuery` for all graph reads: `answer_why`, `fetch_adr`, `list_adrs`, and snapshot validation as needed.
- [FR-5] Expose MCP surfaces for `answer_why`, `fetch_adr`, and `list_adrs`; optional resource aliases are allowed if they wrap the same read-only query port.
- [FR-6] Return serialized domain DTOs with citations/provenance; never return LlamaIndex objects, storage handles, SQLite handles, or internal graph adapter types.
- [FR-7] Enforce input bounds for question length, status filters, `limit`, repository key, ADR id, code area id, and snapshot id.
- [FR-8] Map query-port exceptions to safe MCP errors without exposing secrets, filesystem paths beyond configured safe paths, raw stack traces, or cross-repository data.
- [FR-9] Emit metadata-only observability through the feature 002 `Observability` port.
- [FR-10] Prove no write/mutation dependencies are imported or injected into MCP server construction.

## Non-Functional Requirements

- [NFR-1] Strict read-only behavior: no MCP capability performs writes, approvals, publication, SCM fetches, graph mutations, or config changes.
- [NFR-2] Local PoC transport is stdio only; HTTP/OAuth MCP is deferred.
- [NFR-3] Queries are deterministic, repository-scoped, bounded, and safe for a read-only process sharing same-host graph persistence with the workflow writer.
- [NFR-4] Responses include citations to approved ADRs/evidence when context is found; absence of context is reported explicitly.
- [NFR-5] Testability: server registration, handler validation, serialization, error mapping, read-only dependency wiring, and observability metadata are unit/integration-testable with fake `ArchitectureContextQuery` and `NoOpObservability`.
- [NFR-6] Maintainability: MCP SDK usage is wrapped behind a small app module so SDK/API maturity risk is isolated.

## Scope

### In Scope
- Stdio MCP server app bootstrap and entry point wiring for `living-adr-mcp`.
- Tool/resource definitions for `answer_why`, `fetch_adr`, and `list_adrs`.
- Repository scoping and config binding via feature 002.
- Read-side graph context access via feature 007's implementation of `ArchitectureContextQuery`.
- DTO serialization, safe errors, bounded inputs, citation-bearing responses, and metadata observability.
- Tests and documentation for local MCP host configuration assumptions.

### Out of Scope
- Any graph writes or mutation APIs, including approve/edit/reject, publish-back, supersede, retract, migrate, or rebuild write operations.
- Direct use or redefinition of `ArchitectureGraphStore`, graph adapter internals, LlamaIndex types, or approval capability semantics.
- GitHub/SCM credentials, webhook ingestion, PR/diff fetch, Claude calls, ADR drafting, HITL UI, publish-back, or LangGraph orchestration.
- HTTP/Streamable HTTP MCP transport, OAuth, enterprise identity, remote shared MCP hosting, and broad IDE extension UX.
- Retrieval ranking improvements beyond what `ArchitectureContextQuery` already provides.

## Dependencies and Contract Bindings

- **Feature 007 / 006 graph query seam:** This feature consumes `ArchitectureContextQuery` only. It must not bypass the property-graph port, import LlamaIndex internals, or redefine query DTOs.
- **Feature 002 configuration:** This feature consumes `RepositoryIdentity`, `RepositoryConfig`, `LivingADRConfig`, startup config diagnostics, and `NoOpObservability`/`Observability` contracts.
- **Architecture anchors:** `..\..\architecture.md#tech-stack`, `..\..\architecture.md#service-boundaries`, `..\..\architecture.md#data-model`, `..\..\architecture.md#cross-cutting`, `..\..\architecture.md#anti-patterns`, `..\..\architecture.md#deployment`, `..\..\architecture.md#repositories`.

## Resolved Defaults

- **Transport:** stdio only for PoC.
- **Repository selection:** require a configured repository key when multiple repositories exist; a single configured repository may be used as the default only in app bootstrap, not through a separate code path.
- **Query limit:** default `limit = 5`; clamp to a maximum of 10.
- **Question length:** default maximum 2,000 characters.
- **ADR id/status validation:** validate before calling the query port and map unsupported values to safe user-facing errors.
- **Observability:** metadata-only; no raw ADR bodies, prompts, graph paths, retrieved context, secrets, or stack traces.

## Success Criteria

- [ ] MCP server starts over stdio with valid feature 002 config and fails fast on invalid config.
- [ ] `answer_why`, `fetch_adr`, and `list_adrs` call only `ArchitectureContextQuery` and return citation-bearing serialized DTOs.
- [ ] Unknown repositories, invalid inputs, stale snapshots, missing ADRs, and query failures produce safe MCP errors.
- [ ] Tests prove no mutation/write-side dependencies are injected into or imported by the MCP server.
- [ ] Metadata-only observability is emitted through the feature 002 port.
- [ ] Documentation shows local MCP host configuration without secrets or write credentials.

## Open Questions

No blocking open questions remain. Autopilot planning defaults above are accepted for implementation readiness; HTTP/OAuth transport, remote hosting, and advanced retrieval evaluation remain post-PoC or feature 013 concerns.
