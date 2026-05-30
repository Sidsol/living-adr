"""Observability core port + no-op implementation (feature 002, slice 5).

This module defines a thin, metadata-first instrumentation boundary that lives in
``core`` with **no LangSmith dependency**. Later features (003/008/009/010/012)
instrument against :class:`Observability`; feature 013 swaps in the real
LangSmith-backed adapter without forcing a LangSmith import into workflow, MCP,
GitHub, HITL, graph, or drafting code.

Default-deny raw export contract (architecture #cross-cutting, FM-21)
--------------------------------------------------------------------
Implementations MUST treat the following as **default-deny** payloads and must
never export them as observability metadata without explicit, feature-013-owned
redaction: raw diffs, full prompts, provisional ADR drafts, reviewer comments,
secrets, and retrieved context. Only small, non-sensitive metadata (identifiers,
counts, repository canonical keys, durations, status enums) is permitted here.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol, runtime_checkable

Metadata = Mapping[str, object] | None


class ObservationSpan:
    """A lightweight span handle yielded by :meth:`Observability.start_span`.

    The no-op span records nothing. Real implementations may attach metadata and
    nested events, but the same default-deny raw-export rules apply: only
    non-sensitive metadata may be recorded.
    """

    def __init__(self, name: str, metadata: Metadata = None) -> None:
        self.name = name
        self.metadata: dict[str, object] = dict(metadata or {})

    def record_event(self, name: str, metadata: Metadata = None) -> None:
        """Record a metadata-only event within this span (no-op by default)."""

        return None

    def set_metadata(self, key: str, value: object) -> None:
        """Attach a single non-sensitive metadata value to this span."""

        self.metadata[key] = value


@runtime_checkable
class Observability(Protocol):
    """Metadata-only instrumentation port: events, counters, and spans."""

    def record_event(self, name: str, metadata: Metadata = None) -> None: ...

    def increment_counter(
        self, name: str, value: int = 1, metadata: Metadata = None
    ) -> None: ...

    def start_span(
        self, name: str, metadata: Metadata = None
    ) -> AbstractContextManager[ObservationSpan]: ...


class NoOpObservability:
    """Dependency-free no-op implementation of :class:`Observability`.

    Every method accepts metadata-only payloads and performs no network I/O,
    storage, or raising for normal inputs. It honours the module's default-deny
    raw-export contract trivially by discarding everything it is given (raw
    diffs, prompts, drafts, reviewer comments, secrets, and context are never
    exported).
    """

    def record_event(self, name: str, metadata: Metadata = None) -> None:
        return None

    def increment_counter(
        self, name: str, value: int = 1, metadata: Metadata = None
    ) -> None:
        return None

    @contextmanager
    def start_span(
        self, name: str, metadata: Metadata = None
    ) -> Iterator[ObservationSpan]:
        """Yield a no-op span; exits cleanly on both success and exception."""

        yield ObservationSpan(name, metadata)


__all__ = [
    "Observability",
    "ObservationSpan",
    "NoOpObservability",
    "Metadata",
]
