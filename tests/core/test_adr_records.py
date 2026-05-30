"""Slice 2 (US-2, US-6) tests: ADRRecord authority and source hierarchy.

These tests pin the source-of-truth discipline: approved ``ADRRecord`` objects
are canonical rationale, graph nodes/edges are projections, and a projection
that conflicts with an ADR record is rebuilt or flagged — never silently
overwritten. An ``ADRRecord`` is invalid without repository scope and approved
decision linkage.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from living_adr.core.adr import (
    SOURCE_OF_TRUTH_HIERARCHY,
    ADRRecord,
    ADRRecordRepository,
    ADRStatus,
    ProjectionConflict,
    ProjectionConflictResolution,
)
from living_adr.core.repository import RepositoryIdentity


def repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="alpha", repo_id="42"
    )


def record(**overrides: object) -> ADRRecord:
    base: dict[str, object] = dict(
        repository=repo(),
        adr_id="adr-1",
        title="Split payments service",
        status=ADRStatus.APPROVED,
        content_hash="a" * 64,
        decision_id="decision-1",
    )
    base.update(overrides)
    return ADRRecord(**base)  # type: ignore[arg-type]


# ----------------------------------------------------------------- ADRRecord


def test_adr_record_requires_repository() -> None:
    with pytest.raises(ValidationError):
        ADRRecord(
            adr_id="adr-1",
            title="x",
            status=ADRStatus.APPROVED,
            content_hash="a" * 64,
            decision_id="decision-1",
        )  # type: ignore[call-arg]


def test_adr_record_requires_decision_linkage() -> None:
    with pytest.raises(ValidationError):
        record(decision_id="   ")


def test_adr_record_requires_content_hash() -> None:
    with pytest.raises(ValidationError):
        record(content_hash="")


def test_adr_record_valid_construction_is_immutable() -> None:
    rec = record()
    assert rec.status is ADRStatus.APPROVED
    assert rec.decision_id == "decision-1"
    with pytest.raises(ValidationError):
        rec.title = "tampered"  # type: ignore[misc]


def test_adr_status_includes_lifecycle_states() -> None:
    values = {s.value for s in ADRStatus}
    assert {"proposed", "approved", "superseded", "retracted"} <= values


# ----------------------------------------------------------- source hierarchy


def test_source_of_truth_hierarchy_orders_evidence_record_projection() -> None:
    assert SOURCE_OF_TRUTH_HIERARCHY == (
        "evidence",
        "approved_adr_record",
        "graph_projection",
    )


def test_projection_conflict_resolution_has_no_silent_overwrite() -> None:
    values = {r.value for r in ProjectionConflictResolution}
    assert values == {"rebuild_projection", "flag_for_review"}
    assert "silent_overwrite" not in values
    assert "overwrite" not in values


def test_projection_conflict_is_repository_scoped() -> None:
    conflict = ProjectionConflict(
        repository=repo(),
        adr_id="adr-1",
        node_id="node-1",
        detail="graph node disagrees with approved ADR rationale",
        resolution=ProjectionConflictResolution.REBUILD_PROJECTION,
    )
    assert conflict.resolution is ProjectionConflictResolution.REBUILD_PROJECTION
    assert conflict.repository.key.endswith("/alpha")


# ----------------------------------------------------- ADRRecordRepository port


def test_adr_record_repository_is_runtime_checkable_protocol() -> None:
    class GoodRepo:
        def save(self, repository: RepositoryIdentity, record: ADRRecord) -> ADRRecord:
            return record

        def get(
            self, repository: RepositoryIdentity, adr_id: str
        ) -> ADRRecord | None:
            return None

        def list_approved(
            self, repository: RepositoryIdentity
        ) -> tuple[ADRRecord, ...]:
            return ()

        def resolve_projection_conflict(
            self, repository: RepositoryIdentity, conflict: ProjectionConflict
        ) -> ProjectionConflictResolution:
            return conflict.resolution

    class MissingMethod:
        def save(self, repository: RepositoryIdentity, record: ADRRecord) -> ADRRecord:
            return record

    assert isinstance(GoodRepo(), ADRRecordRepository)
    assert not isinstance(MissingMethod(), ADRRecordRepository)


def test_repository_contract_documents_canonical_authority() -> None:
    doc = (ADRRecordRepository.__doc__ or "").lower()
    assert "canonical" in doc or "authoritative" in doc
    assert "projection" in doc
