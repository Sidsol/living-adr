"""Safe structured logging for observability (feature 013, slice 2).

Emits JSON-compatible, metadata-only log records for events, counters, spans, and
redaction diagnostics. The logger assumes its inputs are already redacted by
:mod:`living_adr.observability.redaction`; it never serialises raw values and the
redaction records describe only paths/reasons, never the stripped content.

Each ``log_*`` method returns the record dict it logged so callers and tests can
assert on the safe shape without parsing log output.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping

from living_adr.observability.redaction import Redaction

_LOG = logging.getLogger("living_adr.observability")


class SafeStructuredLogger:
    """Produces and emits safe, metadata-only structured log records."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger or _LOG

    def log_event(
        self, name: str, metadata: Mapping[str, object]
    ) -> dict[str, object]:
        record = {"kind": "event", "name": name, "metadata": dict(metadata)}
        self._log.info("observability.event", extra={"observability": record})
        return record

    def log_counter(
        self, name: str, value: int, metadata: Mapping[str, object]
    ) -> dict[str, object]:
        record = {
            "kind": "counter",
            "name": name,
            "value": value,
            "metadata": dict(metadata),
        }
        self._log.info("observability.counter", extra={"observability": record})
        return record

    def log_span(
        self,
        name: str,
        metadata: Mapping[str, object],
        error: str | None = None,
    ) -> dict[str, object]:
        record = {
            "kind": "span",
            "name": name,
            "metadata": dict(metadata),
            "error": error,
        }
        self._log.info("observability.span", extra={"observability": record})
        return record

    def log_redaction(
        self, name: str, redactions: Iterable[Redaction]
    ) -> dict[str, object]:
        record = {
            "kind": "redaction",
            "name": name,
            "redactions": [
                {"path": r.path, "key": r.key, "reason": r.reason}
                for r in redactions
            ],
        }
        self._log.info("observability.redaction", extra={"observability": record})
        return record


__all__ = ["SafeStructuredLogger"]
