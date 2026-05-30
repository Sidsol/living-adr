"""Observability provider factory (feature 013, slice 1).

Selects between the dependency-free :class:`NoOpObservability` (feature 002) and
the LangSmith-backed adapter based on :class:`LangSmithSettings`. Callers receive
an :class:`Observability` — they never know which implementation they got, and
never import the LangSmith SDK.

Fail-closed: if the adapter or its sink cannot be constructed, the factory falls
back to no-op behavior rather than raising at startup (US-5, NFR-4).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.observability.config import LangSmithSettings
from living_adr.observability.langsmith_adapter import (
    LangSmithObservability,
    TraceSink,
)

_LOG = logging.getLogger("living_adr.observability")

SinkBuilder = Callable[[LangSmithSettings], TraceSink]


def _default_sink_builder(settings: LangSmithSettings) -> TraceSink:
    # Lazy import keeps the SDK out of the factory's import graph.
    from living_adr.observability.langsmith_sink import build_langsmith_sink

    return build_langsmith_sink(settings)


def build_observability(
    settings: LangSmithSettings,
    *,
    sink: TraceSink | None = None,
    sink_builder: SinkBuilder | None = None,
    metadata_preparer: object | None = None,
    logger: logging.Logger | None = None,
) -> Observability:
    """Return the configured :class:`Observability` implementation.

    With no/invalid LangSmith config, returns :class:`NoOpObservability`. With a
    valid config, returns a :class:`LangSmithObservability` bound to ``sink`` (or
    one built by ``sink_builder``). Any construction failure falls back to no-op.
    """

    log = logger or _LOG
    if not settings.should_enable:
        return NoOpObservability()

    resolved_sink = sink
    if resolved_sink is None:
        builder = sink_builder or _default_sink_builder
        try:
            resolved_sink = builder(settings)
        except Exception:  # noqa: BLE001 — fail closed to no-op (US-5)
            log.warning(
                "LangSmith sink construction failed; falling back to no-op "
                "observability"
            )
            return NoOpObservability()

    return LangSmithObservability(
        resolved_sink,
        settings,
        metadata_preparer=metadata_preparer,  # type: ignore[arg-type]
        logger=log,
    )


__all__ = ["build_observability", "SinkBuilder"]
