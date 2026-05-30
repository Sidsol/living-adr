"""Slice 1 (US-1) tests: core graph value objects.

These tests pin the stable, backend-agnostic graph vocabulary defined by
feature 006. They assert that every value crossing a port boundary is
repository-scoped, that relationship labels are validated deterministically,
and that query result DTOs expose only domain citations/provenance — never a
concrete backend object.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from living_adr.core.graph.models import (
    ADRPath,
    ADRRef,
    ConformanceReport,
    GraphEdge,
    GraphSnapshotRef,
    MigrationResult,
    NodeId,
    ProvenancedADR,
    RelationshipType,
    SchemaVersion,
    UnsupportedRelationshipError,
    WhyAnswer,
)
from living_adr.core.repository import RepositoryIdentity


def repo(repo: str = "alpha") -> RepositoryIdentity:
    return RepositoryIdentity(host="github.com", owner="acme", repo=repo, repo_id="42")


def node(value: str = "n1", repository: RepositoryIdentity | None = None) -> NodeId:
    return NodeId(repository=repository or repo(), value=value)


# --------------------------------------------------------------------- NodeId


def test_node_id_requires_repository_scope() -> None:
    with pytest.raises(ValidationError):
        NodeId(value="n1")  # type: ignore[call-arg]


def test_node_id_rejects_empty_value() -> None:
    with pytest.raises(ValidationError):
        NodeId(repository=repo(), value="   ")


def test_node_id_is_immutable() -> None:
    n = node()
    with pytest.raises(ValidationError):
        n.value = "other"  # type: ignore[misc]


# ----------------------------------------------------------- RelationshipType


def test_minimal_relationship_label_set_is_present() -> None:
    labels = {r.value for r in RelationshipType}
    assert {
        "addresses_component",
        "cites_evidence",
        "supersedes",
        "retracts",
        "records_structural_change",
    } <= labels


def test_unsupported_relationship_label_fails_deterministically() -> None:
    with pytest.raises(UnsupportedRelationshipError):
        RelationshipType.from_label("not_a_real_label")


def test_known_relationship_label_round_trips() -> None:
    assert RelationshipType.from_label("supersedes") is RelationshipType.SUPERSEDES


# -------------------------------------------------------------------- GraphEdge


def test_graph_edge_requires_matching_repository_scope() -> None:
    with pytest.raises(ValidationError):
        GraphEdge(
            repository=repo("alpha"),
            from_node=node("a", repo("alpha")),
            to_node=node("b", repo("beta")),
            relationship=RelationshipType.SUPERSEDES,
        )


def test_graph_edge_valid_construction() -> None:
    edge = GraphEdge(
        repository=repo(),
        from_node=node("a"),
        to_node=node("b"),
        relationship=RelationshipType.CITES_EVIDENCE,
    )
    assert edge.relationship is RelationshipType.CITES_EVIDENCE
    assert edge.from_node.repository == edge.to_node.repository


# ----------------------------------------------------- SchemaVersion / migration


def test_schema_version_orders_and_labels() -> None:
    v1 = SchemaVersion(major=1, minor=0)
    v2 = SchemaVersion(major=1, minor=3)
    assert v1.label == "v1.0"
    assert v2.is_newer_than(v1)
    assert not v1.is_newer_than(v2)


def test_migration_result_is_repository_scoped() -> None:
    result = MigrationResult(
        repository=repo(),
        from_version=SchemaVersion(major=1, minor=0),
        to_version=SchemaVersion(major=1, minor=1),
        applied=True,
    )
    assert result.repository.key == "github.com/acme/alpha"
    assert result.applied is True


def test_graph_snapshot_ref_is_repository_scoped() -> None:
    snap = GraphSnapshotRef(
        repository=repo(),
        snapshot_id="snap-1",
        schema_version=SchemaVersion(major=1, minor=0),
    )
    assert snap.repository.key.endswith("/alpha")


# -------------------------------------------------------- ConformanceReport DTO


def test_conformance_report_tracks_violations() -> None:
    ok = ConformanceReport(repository=repo(), adapter_name="fake", passed=True)
    bad = ConformanceReport(
        repository=repo(),
        adapter_name="leaky",
        passed=False,
        violations=("returned a backend object",),
    )
    assert ok.ok is True
    assert bad.ok is False
    assert bad.violations == ("returned a backend object",)


# ------------------------------------------------------------- query DTO shapes


def test_provenanced_adr_exposes_citations_not_backends() -> None:
    ref = ADRRef(repository=repo(), adr_id="adr-1", title="Pick X", status="approved")
    prov = ProvenancedADR(
        repository=repo(),
        adr=ref,
        citations=("adr:adr-1", "evidence:e-1"),
    )
    assert prov.adr.adr_id == "adr-1"
    assert "adr:adr-1" in prov.citations
    # No backend object: every field is a domain value or scalar/collection.
    assert all(isinstance(c, str) for c in prov.citations)


def test_adr_path_carries_edges_and_adrs() -> None:
    ref = ADRRef(repository=repo(), adr_id="adr-1", title="Pick X", status="approved")
    edge = GraphEdge(
        repository=repo(),
        from_node=node("code:area"),
        to_node=node("adr:adr-1"),
        relationship=RelationshipType.ADDRESSES_COMPONENT,
    )
    path = ADRPath(
        repository=repo(),
        code_area_id="svc/payments",
        edges=(edge,),
        adrs=(ref,),
    )
    assert path.adrs[0].adr_id == "adr-1"
    assert path.edges[0].relationship is RelationshipType.ADDRESSES_COMPONENT


def test_why_answer_repository_scoped_with_provenance() -> None:
    ans = WhyAnswer(
        repository=repo(),
        question="why payments split?",
        answer="See ADR-1.",
        adr_id="adr-1",
        citations=("adr:adr-1",),
        found=True,
    )
    assert ans.found is True
    assert ans.repository.key.endswith("/alpha")
