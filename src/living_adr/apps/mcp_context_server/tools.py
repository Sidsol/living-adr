"""Read-only MCP tool handlers + registry (feature 012).

Each handler is a plain synchronous function over
:class:`McpServerDependencies` and a JSON-like arguments mapping. They validate
and bound untrusted inputs, resolve a configured repository, call **only** the
read-side :class:`ArchitectureContextQueryPort`, serialize domain DTOs, and map
failures to safe MCP errors. The SDK boundary (``app.py``) adapts these into the
async tool surface.

No handler performs writes, approvals, publication, SCM fetches, graph
mutations, or config changes (NFR-1, FR-10).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from mcp.types import Tool

from living_adr.apps.mcp_context_server.dependencies import McpServerDependencies
from living_adr.apps.mcp_context_server.errors import to_safe_error
from living_adr.apps.mcp_context_server.serializers import serialize_adr_ref
from living_adr.apps.mcp_context_server.validation import (
    McpValidationError,
    resolve_repository,
    validate_status,
)

Handler = Callable[[McpServerDependencies, Mapping[str, object]], dict[str, object]]

#: Statuses the read-only surface understands. Anything else is rejected as a
#: safe ``invalid_request`` rather than silently returning empty results.
SUPPORTED_ADR_STATUSES = frozenset(
    {"approved", "superseded", "retracted", "deprecated", "proposed", "accepted"}
)


def list_adrs_handler(
    deps: McpServerDependencies, arguments: Mapping[str, object]
) -> dict[str, object]:
    """List approved ADRs for a configured repository (optional status filter)."""

    identity = resolve_repository(
        deps.config, arguments.get("repository"), deps.limits
    )
    status = validate_status(arguments.get("status"), deps.limits)
    if status is not None and status not in SUPPORTED_ADR_STATUSES:
        raise McpValidationError(f"Unsupported status filter: {status!r}.")

    refs = deps.query.list_adrs(identity)
    if status is not None:
        refs = tuple(r for r in refs if r.status.lower() == status)

    return {
        "repository": identity.key,
        "count": len(refs),
        "adrs": [serialize_adr_ref(r) for r in refs],
    }


# --------------------------------------------------------------------- registry
# Slices append to these in dependency order (list_adrs, fetch_adr, answer_why).
TOOL_HANDLERS: dict[str, Handler] = {
    "list_adrs": list_adrs_handler,
}

TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="list_adrs",
        description=(
            "List approved architecture decision records (ADRs) for a configured "
            "repository, with an optional status filter. Read-only."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repository": {
                    "type": "string",
                    "description": "Canonical host/owner/repo key.",
                },
                "status": {
                    "type": "string",
                    "description": "Optional ADR status filter.",
                },
            },
            "required": ["repository"],
        },
    ),
]


def make_dispatch(
    deps: McpServerDependencies,
) -> Callable[[str, Mapping[str, object]], dict[str, object]]:
    """Bind ``deps`` into a synchronous ``(name, arguments) -> mapping`` dispatch.

    Unknown tools and any handler exception are converted to safe MCP errors so
    the boundary never raises adapter internals at the caller.
    """

    def dispatch(name: str, arguments: Mapping[str, object]) -> dict[str, object]:
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            return to_safe_error(McpValidationError(f"Unknown tool: {name!r}"))
        try:
            return handler(deps, arguments)
        except Exception as exc:  # noqa: BLE001 - mapped to a safe error mapping
            return to_safe_error(exc)

    return dispatch


__all__ = [
    "Handler",
    "SUPPORTED_ADR_STATUSES",
    "list_adrs_handler",
    "TOOL_HANDLERS",
    "TOOL_DEFINITIONS",
    "make_dispatch",
]
