# Implementation Outline: mcp-context-server

## Slice Summary

Feature 012 is planned as **6 independently testable vertical slices**. Each slice preserves the read-only boundary and builds on feature 002 config plus feature 007/006 query contracts.

## Vertical Slices

### Slice 1 — MCP app bootstrap and stdio startup

Create the `living-adr-mcp` app boundary, load feature 002 configuration at startup, construct the MCP SDK server over stdio, and expose no tools until handlers are registered by later slices.

**Test focus:** valid config starts; invalid config fails fast; app construction accepts only config/query/observability dependencies.

### Slice 2 — Read-only query wiring and safety guardrails

Introduce handler construction that injects `ArchitectureContextQuery` only, resolves configured repositories, validates common request fields, and blocks forbidden write-side dependencies/capabilities.

**Test focus:** repository resolution, unknown repository errors, forbidden dependency/import checks, capability list contains no mutations.

### Slice 3 — `list_adrs` MCP surface

Expose `list_adrs` as the first MCP tool/resource and serialize `ADRRef` results with repository scope, status, and citation/provenance summaries.

**Test focus:** success with fake query port, status filtering, unsupported status error mapping, cross-repository isolation.

### Slice 4 — `fetch_adr` MCP surface

Expose `fetch_adr` for one ADR id with optional snapshot support and serialize `ProvenancedADR` content, metadata, status, and provenance safely.

**Test focus:** found/missing ADR behavior, snapshot argument pass-through, safe not-found errors, no internal type leakage.

### Slice 5 — `answer_why` MCP surface

Expose `answer_why` with question/code-area/limit validation and return cited `WhyAnswer` responses, including explicit no-approved-context results.

**Test focus:** bounded input validation, limit default/clamp, citation preservation, no-context response, query-port exception mapping.

### Slice 6 — Observability, docs, and conformance hardening

Emit metadata-only observability for all MCP calls, document local MCP host configuration, and add regression tests proving read-only contract, DTO serialization, and stdio registration remain stable.

**Test focus:** metadata whitelist, no raw payload telemetry, docs exist, all surfaces use query port only.

## Machine-Readable Slice List

```yaml
feature_id: '012'
feature_name: mcp-context-server
slice_count: 6
slices:
  - id: '012-s01'
    name: mcp-app-bootstrap-and-stdio-startup
    order: 1
    independently_testable: true
    primary_paths:
      - 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\app.py'
      - 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\startup.py'
      - 'C:\repos\living-adr\tests\apps\mcp_context_server\test_startup.py'
  - id: '012-s02'
    name: read-only-query-wiring-and-safety-guardrails
    order: 2
    independently_testable: true
    primary_paths:
      - 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\dependencies.py'
      - 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\validation.py'
      - 'C:\repos\living-adr\tests\apps\mcp_context_server\test_read_only_wiring.py'
  - id: '012-s03'
    name: list-adrs-mcp-surface
    order: 3
    independently_testable: true
    primary_paths:
      - 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\tools.py'
      - 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\serializers.py'
      - 'C:\repos\living-adr\tests\apps\mcp_context_server\test_list_adrs.py'
  - id: '012-s04'
    name: fetch-adr-mcp-surface
    order: 4
    independently_testable: true
    primary_paths:
      - 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\tools.py'
      - 'C:\repos\living-adr\tests\apps\mcp_context_server\test_fetch_adr.py'
  - id: '012-s05'
    name: answer-why-mcp-surface
    order: 5
    independently_testable: true
    primary_paths:
      - 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\tools.py'
      - 'C:\repos\living-adr\tests\apps\mcp_context_server\test_answer_why.py'
  - id: '012-s06'
    name: observability-docs-and-conformance-hardening
    order: 6
    independently_testable: true
    primary_paths:
      - 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\observability.py'
      - 'C:\repos\living-adr\docs\mcp-context-server.md'
      - 'C:\repos\living-adr\tests\apps\mcp_context_server\test_observability_and_contract.py'
```

## Dependency Notes

- Slices 3, 4, and 5 can be implemented with fake `ArchitectureContextQuery` fixtures once slice 2 supplies shared validation/repository resolution.
- Slice 6 is last because it hardens all tool surfaces and documentation.
- No slice introduces production writes or write-side graph dependencies.
