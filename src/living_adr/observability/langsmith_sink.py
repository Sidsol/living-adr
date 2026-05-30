"""Real LangSmith trace sink (feature 013, slice 1).

Isolated here so the LangSmith SDK import lives in exactly one place. Application,
workflow, HITL, graph, and MCP modules never import this module — they depend on
the core ``Observability`` port and the factory only. The factory imports this
lazily so importing the factory never pulls in the LangSmith SDK.

This sink is intentionally exercised only in environments with real credentials;
unit tests inject a fake recording sink instead, so CI makes no network calls.
"""

from __future__ import annotations

from collections.abc import Mapping

from living_adr.observability.config import LangSmithSettings


class LangSmithClientSink:
    """Adapts the LangSmith ``Client`` to the adapter's :class:`TraceSink`.

    Only safe, already-redacted metadata reaches this class — redaction happens
    upstream in the adapter's metadata preparer (slice 2). This sink merely
    relays prepared metadata to LangSmith runs.
    """

    def __init__(self, settings: LangSmithSettings, client: object) -> None:
        self._settings = settings
        self._client = client
        self._project = settings.project

    def on_event(self, name: str, metadata: Mapping[str, object]) -> None:
        self._client.create_run(  # type: ignore[attr-defined]
            name=name,
            run_type="chain",
            inputs={},
            extra={"metadata": dict(metadata)},
            project_name=self._project,
        )

    def on_counter(
        self, name: str, value: int, metadata: Mapping[str, object]
    ) -> None:
        payload = dict(metadata)
        payload["count"] = value
        self._client.create_run(  # type: ignore[attr-defined]
            name=name,
            run_type="chain",
            inputs={},
            extra={"metadata": payload},
            project_name=self._project,
        )

    def on_span_start(self, name: str, metadata: Mapping[str, object]) -> str:
        run = self._client.create_run(  # type: ignore[attr-defined]
            name=name,
            run_type="chain",
            inputs={},
            extra={"metadata": dict(metadata)},
            project_name=self._project,
        )
        return str(getattr(run, "id", name))

    def on_span_end(
        self, span_id: str, metadata: Mapping[str, object], error: str | None
    ) -> None:
        self._client.update_run(  # type: ignore[attr-defined]
            span_id,
            extra={"metadata": dict(metadata)},
            error=error,
        )


def build_langsmith_sink(settings: LangSmithSettings) -> LangSmithClientSink:
    """Construct a real LangSmith sink. Imports the SDK lazily."""

    from langsmith import Client  # noqa: PLC0415 — lazy: keep SDK out of factory

    client = Client(api_key=settings.api_key, api_url=settings.endpoint)
    return LangSmithClientSink(settings, client)


__all__ = ["LangSmithClientSink", "build_langsmith_sink"]
