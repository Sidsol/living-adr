"""Slice 1: LangSmith adapter configuration and safe no-op fallback.

These tests exercise the adapter offline using a fake recording sink — no real
LangSmith network calls. They prove the adapter binds to feature 002's
``Observability`` port without redefining it, and that the factory falls back to
``NoOpObservability`` when LangSmith is unconfigured or fails to initialise.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from living_adr.core.observability import (
    NoOpObservability,
    Observability,
    ObservationSpan,
)
from living_adr.observability.config import LangSmithSettings
from living_adr.observability.factory import build_observability
from living_adr.observability.langsmith_adapter import LangSmithObservability


class RecordingSink:
    """In-memory fake of the adapter's trace sink. No network."""

    def __init__(self, fail: bool = False) -> None:
        self.events: list[tuple[str, dict]] = []
        self.counters: list[tuple[str, int, dict]] = []
        self.spans: list[dict] = []
        self._fail = fail
        self._next_id = 0

    def on_event(self, name: str, metadata: Mapping[str, object]) -> None:
        if self._fail:
            raise RuntimeError("sink boom")
        self.events.append((name, dict(metadata)))

    def on_counter(
        self, name: str, value: int, metadata: Mapping[str, object]
    ) -> None:
        if self._fail:
            raise RuntimeError("sink boom")
        self.counters.append((name, value, dict(metadata)))

    def on_span_start(self, name: str, metadata: Mapping[str, object]) -> str:
        if self._fail:
            raise RuntimeError("sink boom")
        self._next_id += 1
        span_id = f"span-{self._next_id}"
        self.spans.append(
            {"id": span_id, "name": name, "metadata": dict(metadata), "error": None}
        )
        return span_id

    def on_span_end(
        self, span_id: str, metadata: Mapping[str, object], error: str | None
    ) -> None:
        if self._fail:
            raise RuntimeError("sink boom")
        for span in self.spans:
            if span["id"] == span_id:
                span["error"] = error
                span["ended"] = True


# --------------------------------------------------------------- config / factory


def test_default_settings_are_disabled_and_safe() -> None:
    settings = LangSmithSettings()
    assert settings.enabled is False
    assert settings.should_enable is False
    assert settings.raw_export_debug is False
    assert settings.sampling_rate == 1.0
    assert settings.retention_days == 30


def test_from_env_empty_is_disabled() -> None:
    settings = LangSmithSettings.from_env({})
    assert settings.should_enable is False


def test_from_env_reads_langsmith_vars() -> None:
    settings = LangSmithSettings.from_env(
        {
            "LANGSMITH_ENABLED": "true",
            "LANGSMITH_API_KEY": "ls-secret",
            "LANGSMITH_PROJECT": "living-adr-poc",
            "LANGSMITH_SAMPLING_RATE": "1.0",
            "LANGSMITH_RETENTION_DAYS": "30",
        }
    )
    assert settings.enabled is True
    assert settings.should_enable is True
    assert settings.project == "living-adr-poc"


def test_enabled_without_api_key_is_not_enabled() -> None:
    settings = LangSmithSettings(enabled=True, api_key=None)
    assert settings.should_enable is False


def test_retention_exceeding_max_is_rejected() -> None:
    with pytest.raises(ValueError):
        LangSmithSettings(retention_days=90)


def test_sampling_rate_out_of_range_is_rejected() -> None:
    with pytest.raises(ValueError):
        LangSmithSettings(sampling_rate=1.5)


def test_factory_returns_noop_when_unconfigured() -> None:
    obs = build_observability(LangSmithSettings())
    assert isinstance(obs, NoOpObservability)
    assert isinstance(obs, Observability)


def test_factory_returns_adapter_when_configured() -> None:
    settings = LangSmithSettings(enabled=True, api_key="ls-secret")
    sink = RecordingSink()
    obs = build_observability(settings, sink=sink)
    assert isinstance(obs, LangSmithObservability)
    assert isinstance(obs, Observability)


def test_factory_falls_back_to_noop_when_sink_build_fails() -> None:
    settings = LangSmithSettings(enabled=True, api_key="ls-secret")

    def boom(_settings: LangSmithSettings) -> object:
        raise RuntimeError("cannot build sink")

    obs = build_observability(settings, sink_builder=boom)
    assert isinstance(obs, NoOpObservability)


# ------------------------------------------------------------------ adapter port


def test_adapter_satisfies_observability_protocol() -> None:
    obs = LangSmithObservability(RecordingSink())
    assert isinstance(obs, Observability)


def test_record_event_forwards_to_sink() -> None:
    sink = RecordingSink()
    obs = LangSmithObservability(sink)
    obs.record_event("pr.classified", {"repository": "github.com/o/r"})
    assert sink.events == [("pr.classified", {"repository": "github.com/o/r"})]


def test_increment_counter_forwards_to_sink() -> None:
    sink = RecordingSink()
    obs = LangSmithObservability(sink)
    obs.increment_counter("drafts.created", 3, {"repository": "github.com/o/r"})
    assert sink.counters == [
        ("drafts.created", 3, {"repository": "github.com/o/r"})
    ]


def test_start_span_yields_observation_span_and_ends() -> None:
    sink = RecordingSink()
    obs = LangSmithObservability(sink)
    with obs.start_span("classify", {"repository": "x"}) as span:
        assert isinstance(span, ObservationSpan)
    assert sink.spans[0]["name"] == "classify"
    assert sink.spans[0].get("ended") is True
    assert sink.spans[0]["error"] is None


def test_start_span_records_error_but_reraises_body_exception() -> None:
    sink = RecordingSink()
    obs = LangSmithObservability(sink)
    with pytest.raises(ValueError):
        with obs.start_span("classify"):
            raise ValueError("boom")
    assert sink.spans[0]["error"] is not None
    assert "ValueError" in sink.spans[0]["error"]


# ------------------------------------------------------ reliability: never raise


def test_record_event_swallows_sink_errors() -> None:
    obs = LangSmithObservability(RecordingSink(fail=True))
    # Must not raise — observability is never control flow (NFR-4).
    assert obs.record_event("pr.classified", {"repository": "x"}) is None


def test_increment_counter_swallows_sink_errors() -> None:
    obs = LangSmithObservability(RecordingSink(fail=True))
    assert obs.increment_counter("drafts.created", 1, {"repository": "x"}) is None


def test_start_span_swallows_sink_errors() -> None:
    obs = LangSmithObservability(RecordingSink(fail=True))
    with obs.start_span("classify", {"repository": "x"}) as span:
        assert isinstance(span, ObservationSpan)


# --------------------------------------------------- no direct LangSmith imports


_SDK_IMPORT = re.compile(r"\b(import|from)\s+langsmith\b")


def test_factory_module_does_not_import_langsmith_sdk_at_top_level() -> None:
    import living_adr.observability.factory as factory_mod

    source = inspect.getsource(factory_mod)
    assert _SDK_IMPORT.search(source) is None
    assert not hasattr(factory_mod, "langsmith")


def test_only_langsmith_sink_module_imports_the_sdk() -> None:
    """No src module outside the observability sink imports the LangSmith SDK.

    The single allowed importer is ``observability/langsmith_sink.py`` (and only
    lazily, inside a function). Every other module — apps, workflow, hitl, graph,
    mcp, scm, core — depends on the core ``Observability`` port instead.
    """

    src_root = Path(__file__).resolve().parents[2] / "src" / "living_adr"
    allowed = {src_root / "observability" / "langsmith_sink.py"}
    offenders: list[str] = []
    for py in src_root.rglob("*.py"):
        if py in allowed:
            continue
        text = py.read_text(encoding="utf-8")
        if _SDK_IMPORT.search(text):
            offenders.append(str(py))
    assert offenders == [], f"LangSmith SDK imported outside sink: {offenders}"
