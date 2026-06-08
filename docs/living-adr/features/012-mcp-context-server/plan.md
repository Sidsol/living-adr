# Tactical Plan: mcp-context-server

## Implementation Principles

- Planning only in this CRISPY run; do not write production/application code now.
- During implementation, make the MCP server a thin read-only adapter over feature 007/006 `ArchitectureContextQuery`.
- Bind to feature 002 `LivingADRConfig`, `RepositoryIdentity`, and `Observability` without redefining them.
- Keep stdio as the only PoC transport.

## File-Level Plan

| Path | Planned Role |
|---|---|
| `C:\repos\living-adr\src\living_adr\apps\mcp_context_server\__init__.py` | App package export surface. |
| `C:\repos\living-adr\src\living_adr\apps\mcp_context_server\app.py` | MCP SDK server construction and tool registration composition. |
| `C:\repos\living-adr\src\living_adr\apps\mcp_context_server\startup.py` | Config loading, dependency assembly, console entrypoint support. |
| `C:\repos\living-adr\src\living_adr\apps\mcp_context_server\dependencies.py` | Typed dependency container accepting only config, query port, observability, and limits. |
| `C:\repos\living-adr\src\living_adr\apps\mcp_context_server\validation.py` | Repository, ADR id, status, question, limit, code-area, and snapshot validation. |
| `C:\repos\living-adr\src\living_adr\apps\mcp_context_server\serializers.py` | Domain DTO to MCP-safe response serialization. |
| `C:\repos\living-adr\src\living_adr\apps\mcp_context_server\tools.py` | `list_adrs`, `fetch_adr`, and `answer_why` handler functions/tool registration. |
| `C:\repos\living-adr\src\living_adr\apps\mcp_context_server\errors.py` | Safe error mapping from validation/query failures to MCP errors. |
| `C:\repos\living-adr\src\living_adr\apps\mcp_context_server\observability.py` | Metadata-only call instrumentation via feature 002 `Observability`. |
| `C:\repos\living-adr\tests\apps\mcp_context_server\*.py` | Slice tests with fake query ports and no network/graph database. |
| `C:\repos\living-adr\docs\mcp-context-server.md` | Local stdio MCP host configuration and read-only capability documentation. |
| `C:\repos\living-adr\pyproject.toml` | Add/verify `living-adr-mcp` console script if not already present. |

## Task Graph

```yaml
feature_id: '012'
slice_count: 6
task_count: 18
tasks:
  - id: '012-s01-t01'
    slice: '012-s01'
    title: Create MCP app package skeleton
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\__init__.py', 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\app.py']
    depends_on: []
  - id: '012-s01-t02'
    slice: '012-s01'
    title: Wire startup config loading and stdio entrypoint
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\startup.py', 'C:\repos\living-adr\pyproject.toml']
    depends_on: ['012-s01-t01']
  - id: '012-s01-t03'
    slice: '012-s01'
    title: Test startup success and config failure
    paths: ['C:\repos\living-adr\tests\apps\mcp_context_server\test_startup.py']
    depends_on: ['012-s01-t02']
  - id: '012-s02-t01'
    slice: '012-s02'
    title: Define read-only dependency container
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\dependencies.py']
    depends_on: ['012-s01-t03']
  - id: '012-s02-t02'
    slice: '012-s02'
    title: Add shared request validation and repository resolution
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\validation.py']
    depends_on: ['012-s02-t01']
  - id: '012-s02-t03'
    slice: '012-s02'
    title: Prove forbidden write dependencies are absent
    paths: ['C:\repos\living-adr\tests\apps\mcp_context_server\test_read_only_wiring.py']
    depends_on: ['012-s02-t02']
  - id: '012-s03-t01'
    slice: '012-s03'
    title: Implement ADRRef serialization
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\serializers.py']
    depends_on: ['012-s02-t03']
  - id: '012-s03-t02'
    slice: '012-s03'
    title: Register list_adrs tool
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\tools.py', 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\app.py']
    depends_on: ['012-s03-t01']
  - id: '012-s03-t03'
    slice: '012-s03'
    title: Test list_adrs status and scope behavior
    paths: ['C:\repos\living-adr\tests\apps\mcp_context_server\test_list_adrs.py']
    depends_on: ['012-s03-t02']
  - id: '012-s04-t01'
    slice: '012-s04'
    title: Implement ProvenancedADR serialization
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\serializers.py']
    depends_on: ['012-s03-t03']
  - id: '012-s04-t02'
    slice: '012-s04'
    title: Register fetch_adr tool with snapshot pass-through
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\tools.py']
    depends_on: ['012-s04-t01']
  - id: '012-s04-t03'
    slice: '012-s04'
    title: Test fetch_adr found missing and safe errors
    paths: ['C:\repos\living-adr\tests\apps\mcp_context_server\test_fetch_adr.py', 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\errors.py']
    depends_on: ['012-s04-t02']
  - id: '012-s05-t01'
    slice: '012-s05'
    title: Implement WhyAnswer serialization
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\serializers.py']
    depends_on: ['012-s04-t03']
  - id: '012-s05-t02'
    slice: '012-s05'
    title: Register answer_why tool with bounded inputs
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\tools.py', 'C:\repos\living-adr\src\living_adr\apps\mcp_context_server\validation.py']
    depends_on: ['012-s05-t01']
  - id: '012-s05-t03'
    slice: '012-s05'
    title: Test answer_why citations no-context and limits
    paths: ['C:\repos\living-adr\tests\apps\mcp_context_server\test_answer_why.py']
    depends_on: ['012-s05-t02']
  - id: '012-s06-t01'
    slice: '012-s06'
    title: Add metadata-only observability wrapper
    paths: ['C:\repos\living-adr\src\living_adr\apps\mcp_context_server\observability.py']
    depends_on: ['012-s05-t03']
  - id: '012-s06-t02'
    slice: '012-s06'
    title: Document local MCP host configuration
    paths: ['C:\repos\living-adr\docs\mcp-context-server.md']
    depends_on: ['012-s06-t01']
  - id: '012-s06-t03'
    slice: '012-s06'
    title: Add conformance regression tests for read-only MCP behavior
    paths: ['C:\repos\living-adr\tests\apps\mcp_context_server\test_observability_and_contract.py']
    depends_on: ['012-s06-t02']
```

## Validation Plan

- Run existing `uv run pytest` after implementation.
- Run existing `uv run ruff check` after implementation.
- Add focused tests for each slice before implementation changes.
- Use fake `ArchitectureContextQuery` fixtures for deterministic MCP handler tests.
- Verify no tests require GitHub, Claude, LangSmith, external graph databases, or network access.

## Rollback / Containment

Because the feature adds a separate read-only deployable surface, implementation rollback can remove the `living-adr-mcp` console entrypoint and package without altering workflow mutation paths or graph write contracts.
