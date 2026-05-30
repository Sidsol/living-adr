"""Authoritative ADR record contract and source-of-truth hierarchy (feature 006).

Source-of-truth discipline (architecture #data-model, #cross-cutting, FM-06/FM-23)
---------------------------------------------------------------------------------
LivingADR keeps three layers strictly ordered:

1. **evidence** — code/PR data and ``ChangeEvidence``: raw, immutable, never
   authoritative on its own.
2. **approved ADR record** — an :class:`ADRRecord` whose creation was authorized
   by an approved review decision: the *canonical, authoritative rationale*.
3. **graph projection** — nodes/edges derived from approved ADR records: a
   queryable projection that *cites* the record but is never the source of
   truth.

When a graph projection conflicts with an approved ``ADRRecord``, the ADR record
wins: the projection is rebuilt or flagged for review. It is **never** silently
overwritten (see :class:`ProjectionConflictResolution`).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator

from living_adr.core.repository import RepositoryIdentity

#: Ordered source-of-truth hierarchy: lower index = higher precedence is the
#: *authoritative* layer (``approved_adr_record``), with ``evidence`` as raw
#: input and ``graph_projection`` as a derived, citable view.
SOURCE_OF_TRUTH_HIERARCHY: tuple[str, str, str] = (
    "evidence",
    "approved_adr_record",
    "graph_projection",
)


class ADRStatus(StrEnum):
    """Lifecycle status of an architecture decision record."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ADRRecord(_Frozen):
    """Authoritative approved-decision record — the canonical rationale.

    An ``ADRRecord`` is invalid without repository scope (``repository``) and
    approved-decision linkage (``decision_id``); both are required and the
    decision id must be non-empty. ``content_hash`` is the SHA-256 of the exact
    rendered draft that was approved, so the record is bound to reviewed content
    (architecture #service-boundaries). Graph nodes/edges are projections over
    this record, never a replacement for it.
    """

    repository: RepositoryIdentity
    adr_id: str
    title: str
    status: ADRStatus
    content_hash: str
    decision_id: str
    structural_change_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    markdown: str = ""
    created_at: datetime | None = None

    @field_validator("adr_id", "content_hash", "decision_id")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return stripped


class ProjectionConflictResolution(StrEnum):
    """How a projection/ADR-record conflict is resolved — never overwrite.

    The authoritative ADR record always wins. The only legal resolutions are to
    rebuild the projection from the approved records or to flag the conflict for
    human review. Silently overwriting the ADR record with projection data is
    intentionally not representable.
    """

    REBUILD_PROJECTION = "rebuild_projection"
    FLAG_FOR_REVIEW = "flag_for_review"


class ProjectionConflict(_Frozen):
    """A detected disagreement between a graph projection node and an ADR record."""

    repository: RepositoryIdentity
    adr_id: str
    node_id: str
    detail: str
    resolution: ProjectionConflictResolution


@runtime_checkable
class ADRRecordRepository(Protocol):
    """Repository of authoritative, canonical approved ADR rationale.

    Implementations store ``ADRRecord`` objects as the *canonical, authoritative*
    rationale for a repository scope. Graph nodes/edges are projections derived
    from these records; on conflict the ADR record wins and the projection is
    rebuilt or flagged — never silently overwritten. Every method is
    repository-scoped: an implementation must reject records whose
    ``repository`` does not match the scope argument.
    """

    def save(self, repository: RepositoryIdentity, record: ADRRecord) -> ADRRecord: ...

    def get(
        self, repository: RepositoryIdentity, adr_id: str
    ) -> ADRRecord | None: ...

    def list_approved(
        self, repository: RepositoryIdentity
    ) -> tuple[ADRRecord, ...]: ...

    def resolve_projection_conflict(
        self, repository: RepositoryIdentity, conflict: ProjectionConflict
    ) -> ProjectionConflictResolution: ...


__all__ = [
    "SOURCE_OF_TRUTH_HIERARCHY",
    "ADRStatus",
    "ADRRecord",
    "ProjectionConflictResolution",
    "ProjectionConflict",
    "ADRRecordRepository",
]
