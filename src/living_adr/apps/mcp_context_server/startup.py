"""mcp-context-server startup config loading + stdio entrypoint (feature 012).

Loads and validates the LivingADR configuration through feature 002 contracts
before the MCP context server registers or serves any tools/resources. Invalid
config fails startup so the read-only context surface never serves traffic with
partial configuration (US-1, FR-2, NFR-2).
"""

from __future__ import annotations

from pathlib import Path

import anyio

from living_adr.apps.mcp_context_server.app import McpContextServerApp
from living_adr.apps.startup_base import ConfigStartupBase


class McpContextServerStartup(ConfigStartupBase):
    """Validated config snapshot owned by the mcp-context-server entrypoint."""


def load_startup_config(path: Path | None = None) -> McpContextServerStartup:
    """Load + validate config, raising ``ConfigStartupError`` on failure."""

    return McpContextServerStartup.from_path(path)


async def _serve_stdio(app: McpContextServerApp) -> None:  # pragma: no cover
    """Serve the read-only MCP server over stdio (the only PoC transport)."""

    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.server.run(
            read_stream,
            write_stream,
            app.server.create_initialization_options(),
        )


def main() -> int:  # pragma: no cover - process entrypoint, exercised manually
    """Console entrypoint: fail fast on invalid config, then serve over stdio.

    Wires the validated config, the feature 007 read-only query adapter, and the
    feature 002 Observability port into the MCP server, then serves it over
    stdio (the only PoC transport). Only the read-side adapter is injected — no
    write/mutation/SCM/LLM dependency is constructed here.
    """

    from living_adr.apps.mcp_context_server.app import build_app
    from living_adr.apps.mcp_context_server.dependencies import (
        McpServerDependencies,
    )
    from living_adr.apps.mcp_context_server.observability import (
        build_observability_for_app,
    )
    from living_adr.graph.llamaindex_adapter import (
        LlamaIndexPropertyGraphAdapter,
    )

    startup = load_startup_config()
    deps = McpServerDependencies(
        config=startup.config,
        query=LlamaIndexPropertyGraphAdapter(),
        observability=build_observability_for_app(),
    )
    app = build_app(deps)
    anyio.run(_serve_stdio, app)
    return 0
