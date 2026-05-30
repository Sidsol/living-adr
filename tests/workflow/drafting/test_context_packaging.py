"""S-003 RED tests: graph context packaging (feature 008, US-2).

The packer assembles approved architecture context **only** through feature
007's read-only ``ArchitectureContextQuery`` port (``answer_why`` /
``traverse_from_code_area``), with repository-scoped, bounded calls. It extracts
bounded ADR citations, marks empty context explicitly, orders deterministically,
and never leaks backend objects into the packaged result.
"""

from __future__ import annotations

from living_adr.core.adr_draft import CitationKind
from living_adr.core.graph.models import (
    ADRPath,
    ADRRef,
    ProvenancedADR,
    RelationshipType,
    WhyAnswer,
)
from living_adr.core.models import RepositoryIdentity
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeOperation,
    ChangeType,
    StructuralChange,
)
from living_adr.workflow.drafting.context import (
    DEFAULT_CONTEXT_LIMIT,
    DEFAULT_CONTEXT_MAX_DEPTH,
    ContextRequest,
    PackagedContext,
    build_context_request,
    package_architecture_context,
)


def _repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="widgets", repo_id="r1"
    )


def _change() -> StructuralChange:
    return StructuralChange(
        id="chg-1",
        repository=_repo(),
        source_scm_event_id="evt-1",
        provider_delivery_id="del-1",
        normalized_pr_key="pr-1",
        change_type=ChangeType.DEPENDENCY,
        operation=ChangeOperation.ADDED,
        affected_dependency="requests",
        dependency_ecosystem="python",
        source_paths=("pyproject.toml", "uv.lock"),
        evidence_ids=("ev-1",),
        confidence=0.9,
        reason_code="direct_manifest_add",
        adr_recommendation=ADRRecommendation.DRAFT,
        classifier_name="dependency-change",
        classifier_version="1.0.0",
    )


class FakeContextQuery:
    """Records calls; returns canned approved context (no backend objects)."""

    def __init__(
        self, *, why: WhyAnswer, paths: list[ADRPath] | None = None
    ) -> None:
        self._why = why
        self._paths = paths or []
        self.why_calls: list[dict[str, object]] = []
        self.traverse_calls: list[dict[str, object]] = []

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
        snapshot: object | None = None,
        limit: int = 5,
    ) -> WhyAnswer:
        self.why_calls.append(
            {
                "repository": repository,
                "question": question,
                "code_area_id": code_area_id,
                "limit": limit,
            }
        )
        return self._why

    def traverse_from_code_area(
        self,
        repository: RepositoryIdentity,
        code_area_id: str,
        relationship_types: set[RelationshipType] | None = None,
        max_depth: int = 2,
        snapshot: object | None = None,
    ) -> list[ADRPath]:
        self.traverse_calls.append(
            {
                "repository": repository,
                "code_area_id": code_area_id,
                "max_depth": max_depth,
            }
        )
        return self._paths


def _adr_ref(adr_id: str, title: str = "Existing ADR") -> ADRRef:
    return ADRRef(repository=_repo(), adr_id=adr_id, title=title, status="approved")


def _found_why() -> WhyAnswer:
    return WhyAnswer(
        repository=_repo(),
        question="why?",
        answer="The HTTP client was standardized on requests.",
        adr_id="adr-3",
        citations=("adr-3",),
        found=True,
        provenance=(
            ProvenancedADR(repository=_repo(), adr=_adr_ref("adr-3")),
        ),
    )


def _empty_why() -> WhyAnswer:
    return WhyAnswer(
        repository=_repo(),
        question="why?",
        answer="",
        adr_id=None,
        citations=(),
        found=False,
    )


def test_build_context_request_is_repository_scoped_and_bounded() -> None:
    request = build_context_request(_change())
    assert isinstance(request, ContextRequest)
    assert request.repository == _repo()
    # code_area_id is derived deterministically from the change source paths.
    assert request.code_area_id == "pyproject.toml"
    assert request.max_depth == DEFAULT_CONTEXT_MAX_DEPTH
    assert request.limit == DEFAULT_CONTEXT_LIMIT
    assert "requests" in request.question


def test_package_makes_scoped_bounded_port_calls() -> None:
    query = FakeContextQuery(why=_found_why())
    request = build_context_request(_change())
    package_architecture_context(query, request)

    assert len(query.why_calls) == 1
    assert query.why_calls[0]["repository"] == _repo()
    assert query.why_calls[0]["code_area_id"] == "pyproject.toml"
    assert query.why_calls[0]["limit"] == DEFAULT_CONTEXT_LIMIT
    assert len(query.traverse_calls) == 1
    assert query.traverse_calls[0]["max_depth"] == DEFAULT_CONTEXT_MAX_DEPTH


def test_package_extracts_adr_citations() -> None:
    paths = [
        ADRPath(
            repository=_repo(),
            code_area_id="pyproject.toml",
            adrs=(_adr_ref("adr-9"), _adr_ref("adr-3")),
        )
    ]
    query = FakeContextQuery(why=_found_why(), paths=paths)
    packaged = package_architecture_context(query, build_context_request(_change()))

    assert isinstance(packaged, PackagedContext)
    assert packaged.is_empty is False
    refs = {c.ref for c in packaged.citations}
    assert refs == {"adr-3", "adr-9"}
    assert all(c.kind is CitationKind.ADR for c in packaged.citations)


def test_empty_context_is_marked_explicitly() -> None:
    query = FakeContextQuery(why=_empty_why(), paths=[])
    packaged = package_architecture_context(query, build_context_request(_change()))

    assert packaged.is_empty is True
    assert packaged.empty_marker is not None
    assert "no approved" in packaged.empty_marker.lower()
    assert packaged.citations == ()


def test_citations_are_deterministically_ordered() -> None:
    paths = [
        ADRPath(
            repository=_repo(),
            code_area_id="pyproject.toml",
            adrs=(_adr_ref("adr-9"), _adr_ref("adr-1"), _adr_ref("adr-5")),
        )
    ]
    query = FakeContextQuery(why=_found_why(), paths=paths)
    first = package_architecture_context(query, build_context_request(_change()))
    second = package_architecture_context(query, build_context_request(_change()))
    refs = [c.ref for c in first.citations]
    assert refs == sorted(refs)
    assert first == second


def test_packaged_context_exposes_no_backend_objects() -> None:
    paths = [
        ADRPath(
            repository=_repo(),
            code_area_id="pyproject.toml",
            adrs=(_adr_ref("adr-3"),),
        )
    ]
    query = FakeContextQuery(why=_found_why(), paths=paths)
    packaged = package_architecture_context(query, build_context_request(_change()))
    for item in packaged.items:
        assert isinstance(item.summary, str)
        assert all(isinstance(a, str) for a in item.adr_ids)
