"""MCP server construction for the read-only ``living-adr-mcp`` deployable.

This module is the *only* place feature 012 touches the official Python ``mcp``
SDK. Keeping SDK usage behind a small app boundary isolates SDK/API-maturity
risk (NFR-6) and keeps the domain handlers (``tools.py``) SDK-light and unit
testable.

The server is **read-only by construction**: it registers only the read-side
context tools handed to :func:`build_server`. No tool performs writes,
approvals, publication, SCM fetches, graph mutations, or config changes
(NFR-1, FR-10).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from mcp.server import Server
from mcp.types import TextContent, Tool

SERVER_NAME = "living-adr-mcp"
SERVER_INSTRUCTIONS = (
    "Read-only LivingADR architecture context server. Exposes approved "
    "architecture decision context (list_adrs, fetch_adr, answer_why) through "
    "the feature 007 ArchitectureContextQuery read port. It cannot mutate the "
    "graph, approve or publish ADRs, call SCM/LLM providers, or change config."
)

#: A dispatch callable maps ``(tool_name, arguments)`` to a JSON-serialisable
#: response mapping. It is intentionally synchronous and SDK-free so handlers
#: stay unit testable; :func:`build_server` adapts it to the async SDK surface.
DispatchFn = Callable[[str, Mapping[str, object]], Mapping[str, object]]


@dataclass(frozen=True)
class McpContextServerApp:
    """Wrapper binding the SDK ``Server`` to its registered read-only tools."""

    server: Server
    tool_names: tuple[str, ...]


def build_server(
    *,
    name: str = SERVER_NAME,
    instructions: str = SERVER_INSTRUCTIONS,
    tools: Sequence[Tool] = (),
    dispatch: DispatchFn | None = None,
) -> McpContextServerApp:
    """Construct the read-only MCP server and register its tool surface.

    ``tools`` and ``dispatch`` are supplied by later slices once the read-only
    handlers exist; with the defaults the server exposes no tools, which keeps
    slice 1 a pure bootstrap.
    """

    server: Server = Server(name=name, instructions=instructions)
    tool_list = list(tools)

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return list(tool_list)

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict[str, object]
    ) -> list[TextContent]:
        if dispatch is None:  # pragma: no cover - no tools registered
            raise ValueError(f"Unknown tool: {name!r}")
        result = dispatch(name, arguments or {})
        return [TextContent(type="text", text=json.dumps(result))]

    return McpContextServerApp(
        server=server,
        tool_names=tuple(tool.name for tool in tool_list),
    )


__all__ = [
    "SERVER_NAME",
    "SERVER_INSTRUCTIONS",
    "DispatchFn",
    "McpContextServerApp",
    "build_server",
]
