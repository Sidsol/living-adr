# Tasks: mcp-context-server

## Story 1: Start a local read-only MCP server

### Slice 012-s01 — MCP app bootstrap and stdio startup

- [x] **012-s01-t01 — Create MCP app package skeleton**
  - Add MCP app package files and a small server-construction function.
  - Keep SDK usage localized to the app boundary.
- [x] **012-s01-t02 — Wire startup config loading and stdio entrypoint**
  - Load feature 002 config at startup and add/verify `living-adr-mcp` console script.
  - Use stdio only.
- [x] **012-s01-t03 — Test startup success and config failure**
  - Cover valid config, invalid config, and startup diagnostics.

## Story 2: Preserve read-only query wiring

### Slice 012-s02 — Read-only query wiring and safety guardrails

- [x] **012-s02-t01 — Define read-only dependency container**
  - Accept only `LivingADRConfig`, `ArchitectureContextQuery`, `Observability`, and limits.
- [x] **012-s02-t02 — Add shared request validation and repository resolution**
  - Resolve configured repositories and validate common fields.
- [x] **012-s02-t03 — Prove forbidden write dependencies are absent**
  - Test no mutation services, write graph ports, SCM providers, Claude clients, or HITL services are imported/injected.

## Story 3: Discover approved ADRs

### Slice 012-s03 — `list_adrs` MCP surface

- [x] **012-s03-t01 — Implement ADRRef serialization**
  - Convert `ADRRef` DTOs into MCP-safe structured responses with citations/provenance summaries.
- [x] **012-s03-t02 — Register list_adrs tool**
  - Call `ArchitectureContextQuery.list_adrs` with repository scope and optional status.
- [x] **012-s03-t03 — Test list_adrs status and scope behavior**
  - Cover filters, unsupported statuses, empty results, and cross-repository isolation.

## Story 4: Inspect one approved ADR

### Slice 012-s04 — `fetch_adr` MCP surface

- [x] **012-s04-t01 — Implement ProvenancedADR serialization**
  - Preserve content, metadata, status, citations, and graph projection details without internal type leakage.
- [x] **012-s04-t02 — Register fetch_adr tool with snapshot pass-through**
  - Call `ArchitectureContextQuery.fetch_adr` with repository, ADR id, and optional snapshot.
- [x] **012-s04-t03 — Test fetch_adr found missing and safe errors**
  - Cover found, missing, outside-scope, stale snapshot, and exception mapping.

## Story 5: Answer architecture why questions

### Slice 012-s05 — `answer_why` MCP surface

- [x] **012-s05-t01 — Implement WhyAnswer serialization**
  - Preserve cited ADRs, graph paths, confidence/relevance metadata, and no-context messages.
- [x] **012-s05-t02 — Register answer_why tool with bounded inputs**
  - Validate question length, code area, limit default/clamp, repository key, and snapshot.
- [x] **012-s05-t03 — Test answer_why citations no-context and limits**
  - Cover relevant answer, no approved context, excessive input, query failure, and citation preservation.

## Story 6: Harden observability and operator documentation

### Slice 012-s06 — Observability, docs, and conformance hardening

- [x] **012-s06-t01 — Add metadata-only observability wrapper**
  - Emit tool name, repository key, status, result count, latency bucket, and error type only.
- [x] **012-s06-t02 — Document local MCP host configuration**
  - Show stdio configuration, read-only capability list, and secret-free setup notes.
- [x] **012-s06-t03 — Add conformance regression tests for read-only MCP behavior**
  - Prove all tools use `ArchitectureContextQuery`, no raw telemetry payloads are emitted, and no mutation capabilities exist.

## Consistency Summary

- Slice count: **6**
- Task count: **18**
- Task IDs are unique and align with `outline.md`, `plan.md`, and `implementation-manifest.yaml`.
- All tasks are implementation-planning tasks only; no production code is written by this CRISPY planning run.
