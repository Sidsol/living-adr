"""LangSmith-backed observability package (feature 013).

Public surface for binding feature 002's ``Observability`` port to a LangSmith
adapter. Application code imports :func:`build_observability` and the core port
type only; it never imports the LangSmith SDK directly.
"""

from __future__ import annotations

from living_adr.observability.config import LangSmithSettings
from living_adr.observability.factory import build_observability
from living_adr.observability.langsmith_adapter import (
    LangSmithObservability,
    TraceSink,
)

__all__ = [
    "LangSmithSettings",
    "build_observability",
    "LangSmithObservability",
    "TraceSink",
]
