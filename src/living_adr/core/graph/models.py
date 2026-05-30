"""Core graph value objects — the stable, backend-agnostic graph vocabulary.

Feature 006 defines the typed vocabulary that adapters (feature 007+), the
workflow service, and the MCP context server all share. Nothing in this module
imports a concrete graph backend (LlamaIndex, Neo4j, SQLite, ...): every value
is a LivingADR domain type built on :class:`RepositoryIdentity` plus standard
scalars/collections.

Relationship to the walking-skeleton smoke models
-------------------------------------------------
``living_adr.core.models`` carries feature-001 *smoke-depth* equivalents
(``ADRRef``, ``WhyAnswer``) used by the in-process walking skeleton. This module
is the **stable contract layer** that downstream features import. The smoke
models remain untouched so the existing skeleton keeps working; they are
expected to converge onto these contracts in a later consolidation feature.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from living_adr.core.repository import RepositoryIdentity


class UnsupportedRelationshipError(ValueError):
    """Raised when an unknown relationship label crosses the graph boundary.

    Stringly typed relationship labels invite graph drift and false edges
    (architecture #anti-patterns FM-08/FM-10), so unknown labels fail
    deterministically rather than being silently stored.
    """


class RelationshipType(StrEnum):
    """Minimal, stable set of architecture-graph relationship labels.

    Feature 007 may extend this set, but it must do so by adding members here
    (the single source of truth) rather than passing free-form strings through
    the ports. Use :meth:`from_label` to convert an external string safely.
    """

    ADDRESSES_COMPONENT = "addresses_component"
    CITES_EVIDENCE = "cites_evidence"
    SUPERSEDES = "supersedes"
    RETRACTS = "retracts"
    RECORDS_STRUCTURAL_CHANGE = "records_structural_change"

    @classmethod
    def from_label(cls, label: str) -> RelationshipType:
        """Return the member for ``label`` or raise ``UnsupportedRelationshipError``."""

        try:
            return cls(label)
        except ValueError as exc:  # pragma: no cover - message asserted in tests
            supported = ", ".join(sorted(m.value for m in cls))
            raise UnsupportedRelationshipError(
                f"Unsupported relationship label {label!r}; supported: {supported}."
            ) from exc


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class NodeId(_Frozen):
    """Repository-scoped, opaque handle for a node in the architecture graph.

    The id value is adapter-defined and opaque to callers; the repository scope
    is mandatory so node references can never leak across repositories.
    """

    repository: RepositoryIdentity
    value: str

    @field_validator("value")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("NodeId.value must not be empty or whitespace")
        return stripped


class GraphEdge(_Frozen):
    """A typed, repository-scoped edge between two graph nodes."""

    repository: RepositoryIdentity
    from_node: NodeId
    to_node: NodeId
    relationship: RelationshipType
    reason: str | None = None

    @model_validator(mode="after")
    def _scopes_agree(self) -> GraphEdge:
        scopes = {self.repository, self.from_node.repository, self.to_node.repository}
        if len(scopes) != 1:
            raise ValueError(
                "GraphEdge repository scope must match both endpoint node scopes."
            )
        return self


class SchemaVersion(_Frozen):
    """Graph-projection schema version used by migration/governance hooks."""

    major: int
    minor: int

    @field_validator("major", "minor")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("SchemaVersion components must be non-negative")
        return value

    @property
    def label(self) -> str:
        return f"v{self.major}.{self.minor}"

    def is_newer_than(self, other: SchemaVersion) -> bool:
        return (self.major, self.minor) > (other.major, other.minor)


class GraphSnapshotRef(_Frozen):
    """Reference to an immutable, repository-scoped graph snapshot."""

    repository: RepositoryIdentity
    snapshot_id: str
    schema_version: SchemaVersion
    created_at: datetime | None = None


class MigrationResult(_Frozen):
    """Outcome of a schema migration hook (typed; no DB objects)."""

    repository: RepositoryIdentity
    from_version: SchemaVersion
    to_version: SchemaVersion
    applied: bool
    notes: str = ""


class ConformanceReport(_Frozen):
    """Result of running the adapter conformance contract against an adapter."""

    repository: RepositoryIdentity
    adapter_name: str
    passed: bool
    violations: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.passed and not self.violations


class ADRRef(_Frozen):
    """Lightweight, repository-scoped reference to an approved ADR (a citation)."""

    repository: RepositoryIdentity
    adr_id: str
    title: str
    status: str


class ProvenancedADR(_Frozen):
    """An ADR reference plus its citations and optional snapshot provenance.

    Query ports return *this* — never a backend record — so the read side
    exposes citations/provenance, not concrete persistence objects.
    """

    repository: RepositoryIdentity
    adr: ADRRef
    citations: tuple[str, ...] = ()
    snapshot: GraphSnapshotRef | None = None


class ADRPath(_Frozen):
    """A traversal path from a code area to one or more approved ADRs."""

    repository: RepositoryIdentity
    code_area_id: str
    edges: tuple[GraphEdge, ...] = ()
    adrs: tuple[ADRRef, ...] = ()


class WhyAnswer(_Frozen):
    """Read-only, repository-scoped answer derived from approved ADR context."""

    repository: RepositoryIdentity
    question: str
    answer: str
    adr_id: str | None
    citations: tuple[str, ...]
    found: bool
    provenance: tuple[ProvenancedADR, ...] = ()


def utc_now() -> datetime:
    """Convenience timezone-aware now() for snapshot/migration metadata."""

    return datetime.now(UTC)


__all__ = [
    "UnsupportedRelationshipError",
    "RelationshipType",
    "NodeId",
    "GraphEdge",
    "SchemaVersion",
    "GraphSnapshotRef",
    "MigrationResult",
    "ConformanceReport",
    "ADRRef",
    "ProvenancedADR",
    "ADRPath",
    "WhyAnswer",
    "utc_now",
]
