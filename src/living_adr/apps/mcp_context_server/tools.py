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

import time
from collections.abc import Callable, Mapping

from mcp.types import Tool

from living_adr.apps.mcp_context_server.dependencies import McpServerDependencies
from living_adr.apps.mcp_context_server.errors import AdrNotFoundError, to_safe_error
from living_adr.apps.mcp_context_server.observability import record_tool_call
from living_adr.apps.mcp_context_server.serializers import (
    serialize_adr_ref,
    serialize_provenanced_adr,
    serialize_why_answer,
)
from living_adr.apps.mcp_context_server.validation import (
    McpValidationError,
    clamp_limit,
    resolve_repository,
    validate_adr_id,
    validate_code_area,
    validate_question,
    validate_snapshot_id,
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


def fetch_adr_handler(
    deps: McpServerDependencies, arguments: Mapping[str, object]
) -> dict[str, object]:
    """Fetch one approved ADR with provenance for a configured repository.

    An optional ``snapshot`` id is validated and echoed back; the read port's
    ``fetch_adr`` is snapshot-agnostic, so snapshot pinning is reported to the
    caller rather than silently ignored. A missing/out-of-scope ADR maps to a
    safe not-found error without leaking other repositories' data.
    """

    identity = resolve_repository(
        deps.config, arguments.get("repository"), deps.limits
    )
    adr_id = validate_adr_id(arguments.get("adr_id"), deps.limits)
    snapshot = validate_snapshot_id(arguments.get("snapshot"), deps.limits)

    adr = deps.query.fetch_adr(identity, adr_id)
    if adr is None:
        raise AdrNotFoundError(
            f"ADR {adr_id!r} was not found for the requested repository."
        )

    return {
        "repository": identity.key,
        "adr": serialize_provenanced_adr(adr),
        "snapshot": snapshot,
    }


def answer_why_handler(
    deps: McpServerDependencies, arguments: Mapping[str, object]
) -> dict[str, object]:
    """Answer an architecture why-question with citations (bounded inputs).

    The question is length-bounded and the limit defaults to 5 / clamps to 10.
    The read port returns an explicit no-approved-context ``WhyAnswer`` when
    nothing answers the question, which is preserved verbatim rather than
    synthesising rationale (NFR-4).
    """

    identity = resolve_repository(
        deps.config, arguments.get("repository"), deps.limits
    )
    question = validate_question(arguments.get("question"), deps.limits)
    code_area_id = validate_code_area(arguments.get("code_area_id"), deps.limits)
    snapshot = validate_snapshot_id(arguments.get("snapshot"), deps.limits)
    limit = clamp_limit(arguments.get("limit"), deps.limits)

    answer = deps.query.answer_why(
        identity,
        question,
        code_area_id=code_area_id,
        limit=limit,
    )

    serialized = serialize_why_answer(answer)
    serialized["snapshot"] = snapshot
    return serialized


# --------------------------------------------------------------------- registry
# Slices append to these in dependency order (list_adrs, fetch_adr, answer_why).
TOOL_HANDLERS: dict[str, Handler] = {
    "list_adrs": list_adrs_handler,
    "fetch_adr": fetch_adr_handler,
    "answer_why": answer_why_handler,
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
    Tool(
        name="fetch_adr",
        description=(
            "Fetch one approved ADR with its citations/provenance for a "
            "configured repository. Optional snapshot id. Read-only."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repository": {
                    "type": "string",
                    "description": "Canonical host/owner/repo key.",
                },
                "adr_id": {
                    "type": "string",
                    "description": "The ADR identifier to fetch.",
                },
                "snapshot": {
                    "type": "string",
                    "description": "Optional graph snapshot id to report against.",
                },
            },
            "required": ["repository", "adr_id"],
        },
    ),
    Tool(
        name="answer_why",
        description=(
            "Answer an architecture rationale (why) question for a configured "
            "repository using approved ADR context, with citations. Optional "
            "code_area_id, limit (default 5, max 10), and snapshot. Read-only."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repository": {
                    "type": "string",
                    "description": "Canonical host/owner/repo key.",
                },
                "question": {
                    "type": "string",
                    "description": "The architecture why-question (bounded length).",
                },
                "code_area_id": {
                    "type": "string",
                    "description": "Optional code area to anchor the question.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional result limit (default 5, max 10).",
                },
                "snapshot": {
                    "type": "string",
                    "description": "Optional graph snapshot id to report against.",
                },
            },
            "required": ["repository", "question"],
        },
    ),
]


def _summarize_result(
    result: Mapping[str, object],
) -> tuple[str, int | None, str | None]:
    """Derive metadata-only (status, result_count, error_type) from a result.

    Only structural counts/codes are read — never the answer body, citations, or
    serialized ADR content.
    """

    error = result.get("error")
    if isinstance(error, Mapping):
        error_type = error.get("type")
        return "error", None, str(error_type) if error_type is not None else None
    count = result.get("count")
    if isinstance(count, int):
        return "ok", count, None
    if "adr" in result:  # fetch_adr success returns exactly one ADR
        return "ok", 1, None
    if "found" in result:  # answer_why
        return "ok", (1 if result.get("found") else 0), None
    return "ok", None, None


def make_dispatch(
    deps: McpServerDependencies,
) -> Callable[[str, Mapping[str, object]], dict[str, object]]:
    """Bind ``deps`` into a synchronous ``(name, arguments) -> mapping`` dispatch.

    Unknown tools and any handler exception are converted to safe MCP errors so
    the boundary never raises adapter internals at the caller. Every call emits
    metadata-only telemetry through the injected Observability port.
    """

    def dispatch(name: str, arguments: Mapping[str, object]) -> dict[str, object]:
        raw_repo = arguments.get("repository")
        repository_key = raw_repo if isinstance(raw_repo, str) else None
        start = time.perf_counter()
        handler = TOOL_HANDLERS.get(name)
        try:
            if handler is None:
                raise McpValidationError(f"Unknown tool: {name!r}")
            result = handler(deps, arguments)
        except Exception as exc:  # noqa: BLE001 - mapped to a safe error mapping
            result = to_safe_error(exc)
        elapsed = time.perf_counter() - start

        status, result_count, error_type = _summarize_result(result)
        record_tool_call(
            deps.observability,
            tool=name,
            repository_key=repository_key,
            status=status,
            elapsed_seconds=elapsed,
            result_count=result_count,
            error_type=error_type,
        )
        return result

    return dispatch


__all__ = [
    "Handler",
    "SUPPORTED_ADR_STATUSES",
    "list_adrs_handler",
    "fetch_adr_handler",
    "answer_why_handler",
    "TOOL_HANDLERS",
    "TOOL_DEFINITIONS",
    "make_dispatch",
]