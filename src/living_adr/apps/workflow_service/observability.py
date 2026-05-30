"""Observability bootstrap for the workflow-service app (feature 013, slice 1).

Builds the :class:`Observability` provider from process environment. The app
depends only on the core port type and this helper — never on the LangSmith SDK.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from living_adr.core.observability import Observability
from living_adr.observability.config import LangSmithSettings
from living_adr.observability.factory import build_observability


def build_observability_for_app(
    env: Mapping[str, str] | None = None,
) -> Observability:
    """Return the configured provider; no-op when LangSmith is unconfigured."""

    settings = LangSmithSettings.from_env(env if env is not None else os.environ)
    return build_observability(settings)


__all__ = ["build_observability_for_app"]
