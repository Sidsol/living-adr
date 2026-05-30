"""Default-deny metadata redaction policy (feature 013, slice 2; FM-21).

Central enforcement point for the architecture's default-deny raw-export
contract (``architecture.md#cross-cutting``). Every metadata mapping bound for
LangSmith or structured logs passes through :func:`redact_metadata`, which:

- keeps safe scalars (identifiers, counts, durations, status/role/class enums),
- strips forbidden *raw content* fields (diffs, prompts, drafts, reviewer
  comments, retrieved context, code snippets, secrets, personal data),
- recurses into nested dicts/lists,
- caps oversized strings that could smuggle raw blobs through a safe-looking key,
- drops values of unsupported types, and
- honors **opt-in** raw export only for non-sensitive repositories.

Diagnostics describe *what* was redacted (path + reason + key) but never the raw
value, so the redaction trail itself can never leak.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

# Forbidden substrings that mark a key as carrying raw/sensitive *content*.
FORBIDDEN_KEY_TOKENS: frozenset[str] = frozenset(
    {
        "diff",
        "patch",
        "prompt",
        "draft",
        "body",
        "comment",
        "context",
        "snippet",
        "code",
        "source",
        "secret",
        "password",
        "credential",
        "api_key",
        "apikey",
        "private_key",
        "access_token",
        "token",
        "auth",
        "email",
        "phone",
        "ssn",
        "personal",
        "pii",
        "response",
        "completion",
        "content",
        "message",
        "text",
        "rationale",
    }
)

# Key shapes that are *always* safe even if they contain a forbidden token,
# because they denote identifiers/counts/enums rather than raw content.
SAFE_KEY_SUFFIXES: tuple[str, ...] = (
    "_id",
    "_count",
    "_ms",
    "_seconds",
    "_role",
    "_class",
    "_type",
    "_status",
    "_version",
    "_rate",
    "_days",
    "_total",
    "_hits",
    "_misses",
    "_score",
    "_tokens",
)

SAFE_KEY_EXACT: frozenset[str] = frozenset(
    {
        "repository",
        "repository_key",
        "outcome",
        "status",
        "stage",
        "reason",
        "reason_code",
        "count",
        "found",
        "name",
    }
)

# Strings longer than this are treated as potential raw blobs and redacted even
# under an otherwise-safe key.
MAX_STRING_LENGTH = 512


class RedactionReason(StrEnum):
    """Machine-readable reason codes for a single redaction."""

    FORBIDDEN_KEY = "forbidden_key"
    OVERSIZED_VALUE = "oversized_value"
    UNSUPPORTED_TYPE = "unsupported_type"
    RAW_EXPORT_DENIED_SENSITIVE = "raw_export_denied_sensitive"


@dataclass(frozen=True)
class Redaction:
    """A single redaction diagnostic. Carries no raw value."""

    path: str
    key: str
    reason: RedactionReason


@dataclass(frozen=True)
class RedactionResult:
    """Outcome of redacting one metadata mapping."""

    safe: dict[str, object]
    redactions: tuple[Redaction, ...] = ()
    raw_export_allowed: bool = False


def _key_is_safe_shape(key: str) -> bool:
    lowered = key.lower()
    if lowered in SAFE_KEY_EXACT:
        return True
    return lowered.endswith(SAFE_KEY_SUFFIXES)


def _key_is_forbidden(key: str) -> bool:
    if _key_is_safe_shape(key):
        return False
    lowered = key.lower()
    return any(token in lowered for token in FORBIDDEN_KEY_TOKENS)


def _join(prefix: str, key: str) -> str:
    return f"{prefix}.{key}" if prefix else key


def _redact_value(
    key: str,
    value: object,
    path: str,
    *,
    raw_allowed: bool,
    sink: list[Redaction],
) -> tuple[bool, object]:
    """Return ``(keep, safe_value)`` for one leaf/branch.

    ``keep`` is ``False`` when the value must be dropped entirely.
    """

    # Numeric / boolean / None values are always safe (counts, durations, flags).
    if value is None or isinstance(value, bool | int | float):
        return True, value

    if isinstance(value, str):
        forbidden = _key_is_forbidden(key)
        if forbidden and not raw_allowed:
            sink.append(Redaction(path, key, RedactionReason.FORBIDDEN_KEY))
            return False, None
        if len(value) > MAX_STRING_LENGTH and not raw_allowed:
            sink.append(Redaction(path, key, RedactionReason.OVERSIZED_VALUE))
            return False, None
        return True, value

    if isinstance(value, Mapping):
        nested = _redact_mapping(value, path, raw_allowed=raw_allowed, sink=sink)
        return True, nested

    if isinstance(value, Sequence):
        out: list[object] = []
        for idx, item in enumerate(value):
            keep, safe_item = _redact_value(
                key,
                item,
                f"{path}[{idx}]",
                raw_allowed=raw_allowed,
                sink=sink,
            )
            if keep:
                out.append(safe_item)
        return True, out

    # Anything else (arbitrary objects) cannot be safely serialised.
    sink.append(Redaction(path, key, RedactionReason.UNSUPPORTED_TYPE))
    return False, None


def _redact_mapping(
    metadata: Mapping[str, object],
    prefix: str,
    *,
    raw_allowed: bool,
    sink: list[Redaction],
) -> dict[str, object]:
    safe: dict[str, object] = {}
    for raw_key, value in metadata.items():
        key = str(raw_key)
        path = _join(prefix, key)
        keep, safe_value = _redact_value(
            key, value, path, raw_allowed=raw_allowed, sink=sink
        )
        if keep:
            safe[key] = safe_value
    return safe


def redact_metadata(
    name: str,
    metadata: Mapping[str, object] | None,
    *,
    settings: object | None = None,
    repository_key: str | None = None,
) -> RedactionResult:
    """Apply the default-deny policy to ``metadata``.

    ``settings`` (a :class:`LangSmithSettings`) and ``repository_key`` govern the
    opt-in raw-export branch: raw export is permitted only when debug export is
    enabled *and* the repository is not marked sensitive.
    """

    metadata = metadata or {}

    raw_debug = bool(getattr(settings, "raw_export_debug", False))
    sensitive = False
    if settings is not None and repository_key is not None:
        is_sensitive = getattr(settings, "is_sensitive", None)
        if callable(is_sensitive):
            sensitive = bool(is_sensitive(repository_key))
    raw_allowed = raw_debug and not sensitive

    redactions: list[Redaction] = []
    safe = _redact_mapping(metadata, "", raw_allowed=raw_allowed, sink=redactions)

    # Surface the sensitive-override denial as an explicit reason code so audits
    # can see that a debug raw export was requested but refused.
    if raw_debug and sensitive:
        denied = _diff_forbidden(metadata)
        for path, key in denied:
            redactions.append(
                Redaction(path, key, RedactionReason.RAW_EXPORT_DENIED_SENSITIVE)
            )

    return RedactionResult(
        safe=safe,
        redactions=tuple(redactions),
        raw_export_allowed=raw_allowed,
    )


def _diff_forbidden(
    metadata: Mapping[str, object], prefix: str = ""
) -> list[tuple[str, str]]:
    """List (path, key) for top-level forbidden string keys (sensitive audit)."""

    found: list[tuple[str, str]] = []
    for raw_key, value in metadata.items():
        key = str(raw_key)
        if isinstance(value, str) and _key_is_forbidden(key):
            found.append((_join(prefix, key), key))
    return found


__all__ = [
    "RedactionReason",
    "Redaction",
    "RedactionResult",
    "redact_metadata",
    "FORBIDDEN_KEY_TOKENS",
    "MAX_STRING_LENGTH",
]
