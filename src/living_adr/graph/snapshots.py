"""Read-snapshot references for MCP-safe context delivery.

The MCP context server reads through ``ArchitectureContextQuery`` and may pin a
``GraphSnapshotRef`` so a series of queries observe a consistent projection. A
snapshot here is a *logical revision marker* (``rev-<n>``) rather than a copied
file: it is cheap to mint and lets a reader detect, via
:func:`snapshot_state`, whether the projection advanced underneath it. No write
capability is exposed through any of this (architecture #service-boundaries — MCP
is read-only).
"""

from __future__ import annotations

from enum import StrEnum

from living_adr.core.graph.models import GraphSnapshotRef, SchemaVersion, utc_now
from living_adr.core.repository import RepositoryIdentity

_REV_PREFIX = "rev-"


class SnapshotState(StrEnum):
    """Whether a snapshot still reflects the latest persisted revision."""

    CURRENT = "current"
    STALE = "stale"


def build_snapshot_ref(
    repository: RepositoryIdentity,
    schema_version: SchemaVersion,
    revision: int,
) -> GraphSnapshotRef:
    """Construct a repository-scoped snapshot reference for ``revision``."""

    return GraphSnapshotRef(
        repository=repository,
        snapshot_id=f"{_REV_PREFIX}{revision}",
        schema_version=schema_version,
        created_at=utc_now(),
    )


def snapshot_revision(snapshot: GraphSnapshotRef) -> int:
    """Parse the logical revision out of a ``rev-<n>`` snapshot id."""

    raw = snapshot.snapshot_id
    if not raw.startswith(_REV_PREFIX):
        raise ValueError(f"unrecognized snapshot id {raw!r}")
    return int(raw[len(_REV_PREFIX) :])


def snapshot_state(
    snapshot: GraphSnapshotRef, current_revision: int
) -> SnapshotState:
    """Return ``CURRENT`` iff the snapshot matches the current revision."""

    return (
        SnapshotState.CURRENT
        if snapshot_revision(snapshot) == current_revision
        else SnapshotState.STALE
    )


__all__ = [
    "SnapshotState",
    "build_snapshot_ref",
    "snapshot_revision",
    "snapshot_state",
]
