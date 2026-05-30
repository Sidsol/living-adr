"""Read-only dependency container for the MCP context server (feature 012).

The MCP server is **read-only by construction**: this container accepts only the
read-side :class:`ArchitectureContextQueryPort`, the validated feature 002
:class:`LivingADRConfig`, the feature 002 :class:`Observability` port, and input
limits. It deliberately imports and references *no* write-side graph store,
approval/mutation service, SCM provider, or LLM client, so no mutation path can
be injected into tool handlers (US-5, FR-10, NFR-1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from living_adr.core.config import LivingADRConfig
from living_adr.core.graph.models import (
    ADRRef,
    GraphSnapshotRef,
    ProvenancedADR,
    WhyAnswer,
)
from living_adr.core.observability import Observability
from living_adr.core.repository import RepositoryIdentity


@runtime_checkable
class ArchitectureContextQueryPort(Protocol):
    """Structural read-side port the MCP server is allowed to depend on.

    This mirrors the read methods implemented by the feature 007 graph adapter
    (``list_adrs``, ``fetch_adr``, ``answer_why``). It exposes **no** mutation
    method and accepts no approval credential — a write port cannot satisfy it.
    """

    def list_adrs(self, repository: RepositoryIdentity) -> tuple[ADRRef, ...]: ...

    def fetch_adr(
        self, repository: RepositoryIdentity, adr_id: str
    ) -> ProvenancedADR | None: ...

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
        snapshot: GraphSnapshotRef | None = None,
        limit: int = 5,
    ) -> WhyAnswer: ...


@dataclass(frozen=True)
class QueryLimits:
    """Bounded-input policy for untrusted MCP requests (FR-7).

    Defaults follow the resolved feature defaults: ``answer_why`` limit defaults
    to 5 and clamps to 10; questions are capped at 2,000 characters.
    """

    default_limit: int = 5
    max_limit: int = 10
    max_question_length: int = 2000
    max_repository_key_length: int = 512
    max_adr_id_length: int = 256
    max_status_length: int = 64
    max_code_area_length: int = 512
    max_snapshot_id_length: int = 256


@dataclass(frozen=True)
class McpServerDependencies:
    """Read-only dependency bundle injected into MCP tool handlers."""

    config: LivingADRConfig
    query: ArchitectureContextQueryPort
    observability: Observability
    limits: QueryLimits = field(default_factory=QueryLimits)


__all__ = [
    "ArchitectureContextQueryPort",
    "QueryLimits",
    "McpServerDependencies",
]
