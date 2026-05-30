"""Slice 5 (US-5) — read snapshots and query DTOs for MCP context delivery.

These tests pin the read-side contract the feature 012 MCP server depends on:
``answer_why`` / ``fetch_adr`` / ``list_adrs`` / ``traverse_from_code_area`` return
only feature 006 domain DTOs with ADR citations, reads never mutate graph state,
and ``validate_snapshot_current`` gives a deterministic current/stale answer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from living_adr.core.adr import ADRRecord, ADRStatus
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.models import (
    ADRPath,
    ADRRef,
    ProvenancedADR,
    WhyAnswer,
)
from living_adr.core.repository import RepositoryIdentity
from living_adr.graph import GraphPersistenceConfig, LlamaIndexPropertyGraphAdapter
from living_adr.graph.snapshots import SnapshotState

_HASH = "b" * 64


def _config(tmp_path: Path) -> GraphPersistenceConfig:
    return GraphPersistenceConfig(graph_root=tmp_path / "var" / "graph")


def _repo(repo: str = "alpha", repo_id: str = "42") -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo=repo, repo_id=repo_id
    )


def _adr(repository: RepositoryIdentity, adr_id: str = "adr-1") -> ADRRecord:
    return ADRRecord(
        repository=repository,
        adr_id=adr_id,
        title=f"Decision {adr_id}",
        status=ADRStatus.APPROVED,
        content_hash=_HASH,
        decision_id=f"decision-{adr_id}",
        evidence_ids=("ev-1",),
    )


def _decision(repository: RepositoryIdentity) -> ApprovedReviewDecision:
    return ApprovedReviewDecision(
        repository=repository,
        decision_id="decision-x",
        reviewer_id="lead-1",
        adr_draft_id="draft-1",
        adr_draft_content_hash=_HASH,
        target_fingerprint="fp",
        minted_at=datetime.now(UTC),
    )


def _seeded(
    tmp_path: Path,
) -> tuple[LlamaIndexPropertyGraphAdapter, RepositoryIdentity]:
    adapter = LlamaIndexPropertyGraphAdapter(config=_config(tmp_path))
    repo = _repo()
    adapter.upsert_adr_node(repo, _adr(repo, "adr-1"), _decision(repo))
    adapter.upsert_adr_node(repo, _adr(repo, "adr-2"), _decision(repo))
    return adapter, repo


def test_answer_why_returns_domain_whyanswer_with_citations(tmp_path: Path) -> None:
    adapter, repo = _seeded(tmp_path)
    writes_before = adapter.write_calls
    answer = adapter.answer_why(repo, "why split payments?")
    assert isinstance(answer, WhyAnswer)
    assert type(answer).__module__.startswith("living_adr")
    assert answer.found is True
    assert answer.citations, "why answer must cite at least one approved ADR"
    assert all(isinstance(p, ProvenancedADR) for p in answer.provenance)
    # Reads must not mutate.
    assert adapter.write_calls == writes_before


def test_answer_why_on_empty_repo_is_not_found(tmp_path: Path) -> None:
    adapter = LlamaIndexPropertyGraphAdapter(config=_config(tmp_path))
    answer = adapter.answer_why(_repo("empty", "9"), "why?")
    assert answer.found is False
    assert answer.adr_id is None


def test_list_adrs_returns_scoped_refs(tmp_path: Path) -> None:
    adapter, repo = _seeded(tmp_path)
    refs = adapter.list_adrs(repo)
    assert {r.adr_id for r in refs} == {"adr-1", "adr-2"}
    assert all(isinstance(r, ADRRef) for r in refs)
    assert all(r.repository == repo for r in refs)


def test_fetch_adr_returns_provenanced_dto_or_none(tmp_path: Path) -> None:
    adapter, repo = _seeded(tmp_path)
    got = adapter.fetch_adr(repo, "adr-1")
    assert isinstance(got, ProvenancedADR)
    assert got.adr.adr_id == "adr-1"
    assert got.citations
    assert adapter.fetch_adr(repo, "missing") is None


def test_traverse_returns_adrpaths_and_is_repository_scoped(tmp_path: Path) -> None:
    adapter, repo = _seeded(tmp_path)
    paths = adapter.traverse_from_code_area(repo, "svc/payments")
    assert isinstance(paths, list)
    assert all(isinstance(p, ADRPath) for p in paths)
    # A different repository scope sees nothing.
    assert adapter.traverse_from_code_area(_repo("beta", "77"), "svc/payments") == []


def test_validate_snapshot_current_is_deterministic(tmp_path: Path) -> None:
    adapter, repo = _seeded(tmp_path)
    snapshot = adapter.rebuild_snapshot(repo)
    assert adapter.validate_snapshot_current(repo, snapshot) == SnapshotState.CURRENT
    # A further write advances the revision, making the old snapshot stale.
    adapter.upsert_adr_node(repo, _adr(repo, "adr-3"), _decision(repo))
    assert adapter.validate_snapshot_current(repo, snapshot) == SnapshotState.STALE
    # Validation performs no writes.
    writes_before = adapter.write_calls
    adapter.validate_snapshot_current(repo, snapshot)
    assert adapter.write_calls == writes_before


def test_read_methods_return_no_backend_objects(tmp_path: Path) -> None:
    adapter, repo = _seeded(tmp_path)
    answer = adapter.answer_why(repo, "why?")
    for prov in answer.provenance:
        assert type(prov).__module__.startswith("living_adr")
    for ref in adapter.list_adrs(repo):
        assert type(ref).__module__.startswith("living_adr")
