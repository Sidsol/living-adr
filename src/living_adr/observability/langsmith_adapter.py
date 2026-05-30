"""LangSmith-backed :class:`Observability` adapter (feature 013, slice 1).

Binds to feature 002's core port (``record_event`` / ``increment_counter`` /
``start_span``) **without redefining it**. The adapter forwards metadata-only
payloads to an injectable :class:`TraceSink`; tests inject a fake recording sink
so the adapter is exercised entirely offline (no real LangSmith network calls).

Reliability (NFR-4): observability is never control flow. Every sink interaction
is wrapped so a failing/unreachable LangSmith backend can never raise out of an
instrumentation call and break the workflow, HITL, graph, or MCP paths.

Redaction (the default-deny raw-export policy) is layered in by slice 2 via the
``metadata_preparer`` seam; slice 1 ships an identity preparer.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Protocol

from living_adr.core.observability import Metadata, ObservationSpan

_LOG = logging.getLogger("living_adr.observability")

MetadataPreparer = Callable[[str, Mapping[str, object]], Mapping[str, object]]


class TraceSink(Protocol):
    """Minimal trace sink the adapter writes to.

    A real LangSmith-backed sink is constructed by the factory; tests inject a
    fake recording sink. Keeping this protocol tiny avoids leaking the LangSmith
    SDK surface into the adapter and keeps the seam testable offline.
    """

    def on_event(self, name: str, metadata: Mapping[str, object]) -> None: ...

    def on_counter(
        self, name: str, value: int, metadata: Mapping[str, object]
    ) -> None: ...

    def on_span_start(
        self, name: str, metadata: Mapping[str, object]
    ) -> str: ...

    def on_span_end(
        self, span_id: str, metadata: Mapping[str, object], error: str | None
    ) -> None: ...


def _identity_preparer(
    name: str, metadata: Mapping[str, object]
) -> Mapping[str, object]:
    return dict(metadata)


class LangSmithObservability:
    """:class:`Observability` implementation that forwards to a trace sink."""

    def __init__(
        self,
        sink: TraceSink,
        settings: object | None = None,
        *,
        metadata_preparer: MetadataPreparer | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._sink = sink
        self._settings = settings
        self._prepare = metadata_preparer or _identity_preparer
        self._log = logger or _LOG

    def _safe_metadata(
        self, name: str, metadata: Metadata
    ) -> Mapping[str, object]:
        prepared = self._prepare(name, dict(metadata or {}))
        return dict(prepared)

    def record_event(self, name: str, metadata: Metadata = None) -> None:
        try:
            self._sink.on_event(name, self._safe_metadata(name, metadata))
        except Exception:  # noqa: BLE001 — telemetry must never raise (NFR-4)
            self._log.warning("observability event dropped", extra={"event": name})
        return None

    def increment_counter(
        self, name: str, value: int = 1, metadata: Metadata = None
    ) -> None:
        try:
            self._sink.on_counter(name, value, self._safe_metadata(name, metadata))
        except Exception:  # noqa: BLE001
            self._log.warning("observability counter dropped", extra={"event": name})
        return None

    @contextmanager
    def start_span(
        self, name: str, metadata: Metadata = None
    ) -> Iterator[ObservationSpan]:
        span = ObservationSpan(name, metadata)
        span_id: str | None = None
        try:
            span_id = self._sink.on_span_start(
                name, self._safe_metadata(name, metadata)
            )
        except Exception:  # noqa: BLE001
            self._log.warning("observability span start dropped", extra={"event": name})

        error: str | None = None
        try:
            yield span
        except Exception as exc:  # noqa: BLE001 — re-raised below; body owns flow
            # Record the *type* only — never the message, which could carry
            # sensitive payload content (default-deny raw export).
            error = type(exc).__name__
            raise
        finally:
            if span_id is not None:
                try:
                    self._sink.on_span_end(
                        span_id, self._safe_metadata(name, span.metadata), error
                    )
                except Exception:  # noqa: BLE001
                    self._log.warning(
                        "observability span end dropped", extra={"event": name}
                    )


__all__ = ["LangSmithObservability", "TraceSink", "MetadataPreparer"]
