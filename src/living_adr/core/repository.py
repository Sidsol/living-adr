"""Repository identity seam (feature 002).

``RepositoryIdentity`` is the provider-neutral scope key used by SCM ingestion,
graph writes, MCP reads, publish-back, and observability metadata. The canonical
definition lives in :mod:`living_adr.core.models` (established by feature 001's
walking skeleton). This module re-exports it as the stable import path so feature
002 and later features can depend on ``living_adr.core.repository`` without
duplicating the model definition.
"""

from __future__ import annotations

from living_adr.core.models import RepositoryIdentity

__all__ = ["RepositoryIdentity"]
