"""Safe error mapping for MCP tool failures (feature 012).

Query-port and validation failures are mapped to *safe* MCP error mappings that
never expose secrets, raw stack traces, private filesystem paths, or
cross-repository data (FR-8). Only error codes we author and messages we control
are surfaced; any unexpected exception collapses to a generic message.
"""

from __future__ import annotations

from living_adr.apps.mcp_context_server.validation import (
    McpValidationError,
    UnknownRepositoryError,
)


class AdrNotFoundError(Exception):
    """Raised when a requested ADR does not exist within the repository scope."""

    def __init__(self, message: str = "The requested ADR was not found.") -> None:
        super().__init__(message)


class QueryExecutionError(Exception):
    """Raised when the read-side query port fails for a non-validation reason."""


_GENERIC_QUERY_MESSAGE = (
    "An internal error occurred while reading approved architecture context."
)


def to_safe_error(exc: Exception) -> dict[str, object]:
    """Map an exception to a safe, serialisable MCP error mapping.

    The ``type`` is a stable machine code; the ``message`` is only ever text we
    authored (validation/not-found) or a fixed generic string, so adapter
    internals, stack traces, and secrets can never leak to the caller.
    """

    if isinstance(exc, UnknownRepositoryError):
        return _error("unknown_repository", str(exc))
    if isinstance(exc, McpValidationError):
        return _error("invalid_request", str(exc))
    if isinstance(exc, AdrNotFoundError):
        return _error("not_found", str(exc))
    # QueryExecutionError and any other unexpected exception are collapsed to a
    # generic message — never the raw exception text.
    return _error("query_failed", _GENERIC_QUERY_MESSAGE)


def _error(error_type: str, message: str) -> dict[str, object]:
    return {"error": {"type": error_type, "message": message}}


__all__ = [
    "AdrNotFoundError",
    "QueryExecutionError",
    "to_safe_error",
]
