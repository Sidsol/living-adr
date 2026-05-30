"""Shared request validation + repository resolution (feature 012).

Every MCP request is validated and resolved to a configured
:class:`RepositoryIdentity` *before* the read-side query port is called
(FR-3, FR-7). Untrusted inputs are bounded; failures raise
:class:`McpValidationError` / :class:`UnknownRepositoryError`, which the error
mapper turns into safe MCP errors that never leak the configured repository set,
secrets, or filesystem paths (FR-8).
"""

from __future__ import annotations

from living_adr.apps.mcp_context_server.dependencies import QueryLimits
from living_adr.core.config import LivingADRConfig
from living_adr.core.repository import RepositoryIdentity


class McpValidationError(ValueError):
    """Raised when an untrusted MCP input fails validation/bounds checks."""


class UnknownRepositoryError(McpValidationError):
    """Raised when a request targets a repository that is not configured.

    The message intentionally omits the configured repository keys so the
    read-only surface never enumerates other repositories to a caller (FR-8).
    """


def _require_text(value: object, *, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise McpValidationError(f"{field} must be a string")
    stripped = value.strip()
    if not stripped:
        raise McpValidationError(f"{field} must not be empty or whitespace")
    if len(stripped) > max_length:
        raise McpValidationError(
            f"{field} exceeds the maximum length of {max_length} characters"
        )
    return stripped


def validate_repository_key(
    value: object, limits: QueryLimits | None = None
) -> str:
    """Return a bounded, stripped repository key or raise."""

    limits = limits or QueryLimits()
    return _require_text(
        value, field="repository", max_length=limits.max_repository_key_length
    )


def validate_adr_id(value: object, limits: QueryLimits | None = None) -> str:
    """Return a bounded, stripped ADR id or raise."""

    limits = limits or QueryLimits()
    return _require_text(
        value, field="adr_id", max_length=limits.max_adr_id_length
    )


def validate_status(
    value: object, limits: QueryLimits | None = None
) -> str | None:
    """Return an optional, normalised (lower-cased) status filter or raise."""

    if value is None:
        return None
    limits = limits or QueryLimits()
    return _require_text(
        value, field="status", max_length=limits.max_status_length
    ).lower()


def validate_code_area(
    value: object, limits: QueryLimits | None = None
) -> str | None:
    """Return an optional, bounded code-area id or raise."""

    if value is None:
        return None
    limits = limits or QueryLimits()
    return _require_text(
        value, field="code_area_id", max_length=limits.max_code_area_length
    )


def validate_snapshot_id(
    value: object, limits: QueryLimits | None = None
) -> str | None:
    """Return an optional, bounded snapshot id or raise."""

    if value is None:
        return None
    limits = limits or QueryLimits()
    return _require_text(
        value, field="snapshot", max_length=limits.max_snapshot_id_length
    )


def validate_question(value: object, limits: QueryLimits | None = None) -> str:
    """Return a bounded, stripped question string or raise."""

    limits = limits or QueryLimits()
    return _require_text(
        value, field="question", max_length=limits.max_question_length
    )


def clamp_limit(value: object, limits: QueryLimits | None = None) -> int:
    """Clamp an optional caller limit into ``[1, max_limit]`` with a default.

    ``None`` and non-positive values fall back to the configured default; values
    above the maximum are clamped down rather than rejected (FR-7).
    """

    limits = limits or QueryLimits()
    if value is None:
        return limits.default_limit
    if not isinstance(value, int) or isinstance(value, bool):
        raise McpValidationError("limit must be an integer")
    if value <= 0:
        return limits.default_limit
    return min(value, limits.max_limit)


def resolve_repository(
    config: LivingADRConfig,
    repository_key: object,
    limits: QueryLimits | None = None,
) -> RepositoryIdentity:
    """Resolve a request's repository key to a configured identity, or raise.

    Unknown repositories are rejected before any query runs, and the error never
    enumerates the configured repositories (FR-3, FR-8).
    """

    key = validate_repository_key(repository_key, limits)
    entry = config.get(key)
    if entry is None:
        raise UnknownRepositoryError(
            f"Repository {key!r} is not configured for this MCP context server."
        )
    return entry.identity


__all__ = [
    "McpValidationError",
    "UnknownRepositoryError",
    "validate_repository_key",
    "validate_adr_id",
    "validate_status",
    "validate_code_area",
    "validate_snapshot_id",
    "validate_question",
    "clamp_limit",
    "resolve_repository",
]
