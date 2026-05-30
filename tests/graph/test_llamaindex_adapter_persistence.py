"""Slice 1 (US-1/US-3) — persistence root, path derivation, reopen, no leakage.

These tests pin the adapter's local persistence contract before any graph
behaviour exists: deterministic repository-partitioned paths under ``var\\graph``,
path-traversal safety, initialize/reopen semantics, and the rule that no public
attribute exposes a LlamaIndex storage context or SQLite connection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from living_adr.core.adr import ADRRecord, ADRStatus
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.models import GraphEdge, NodeId, RelationshipType
from living_adr.core.models import StructuralChange
from living_adr.core.repository import RepositoryIdentity
from living_adr.graph import GraphPersistenceConfig, LlamaIndexPropertyGraphAdapter
from living_adr.graph.llamaindex_mapping import adr_node_value
from living_adr.graph.persistence import (
    OpenMode,
    repository_storage_dir,
)
from living_adr.graph.provenance import assert_complete
from living_adr.graph.schema import ADAPTER_SCHEMA_VERSION, SchemaMetadataError


def _repo(repo: str = "alpha", repo_id: str = "42") -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo=repo, repo_id=repo_id
    )


def _config(tmp_path: Path) -> GraphPersistenceConfig:
    return GraphPersistenceConfig(graph_root=tmp_path / "var" / "graph")


def test_storage_path_is_deterministic_and_under_root(tmp_path: Path) -> None:
    config = _config(tmp_path)
    repo = _repo()
    first = repository_storage_dir(config, repo)
    second = repository_storage_dir(config, repo)
    assert first == second, "path derivation must be deterministic"
    root = config.graph_root.resolve()
    assert root == first.parent, "repository dir must live directly under graph root"
    assert str(first).startswith(str(root))


def test_distinct_repositories_get_distinct_collision_resistant_paths(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    # Same key text but different opaque repo_id must not collide.
    a = repository_storage_dir(config, _repo("alpha", "42"))
    b = repository_storage_dir(config, _repo("alpha", "99"))
    c = repository_storage_dir(config, _repo("beta", "42"))
    assert len({a, b, c}) == 3


def test_path_traversal_in_repo_name_is_contained(tmp_path: Path) -> None:
    config = _config(tmp_path)
    hostile = RepositoryIdentity(
        host="github.com", owner="acme", repo="../../etc", repo_id="9"
    )
    target = repository_storage_dir(config, hostile)
    root = config.graph_root.resolve()
    # Containment: the resolved target never escapes the graph root.
    assert root in target.parents or root == target.parent
    assert ".." not in target.relative_to(root).parts


def test_adapter_initializes_and_reopens_repository_graph(tmp_path: Path) -> None:
    config = _config(tmp_path)
    repo = _repo()
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    adapter.initialize_repository(repo)
    storage = repository_storage_dir(config, repo)
    assert storage.exists(), "initialize must create the repository storage dir"

    # A brand-new adapter pointing at the same root must reopen without error.
    reopened = LlamaIndexPropertyGraphAdapter(config=config)
    assert reopened.is_initialized(repo) is True


def test_no_public_llamaindex_or_sqlite_objects_leak(tmp_path: Path) -> None:
    config = _config(tmp_path)
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    adapter.initialize_repository(_repo())
    for name in vars(adapter):
        if name.startswith("_"):
            continue
        value = getattr(adapter, name)
        module = type(value).__module__
        assert not module.startswith("llama_index"), (
            f"public attribute {name!r} leaks a LlamaIndex object"
        )
        assert "sqlite3" not in module, (
            f"public attribute {name!r} leaks a SQLite connection"
        )


def test_open_mode_enum_exposes_read_and_write() -> None:
    assert OpenMode.READ_WRITE != OpenMode.READ_ONLY


def test_init_requires_no_external_service(tmp_path: Path) -> None:
    # Constructing and initializing must not require network/embeddings.
    adapter = LlamaIndexPropertyGraphAdapter(config=_config(tmp_path))
    with pytest.raises(SchemaMetadataError):
        # Querying an uninitialised repo schema version fails deterministically
        # rather than reaching out to anything external.
        adapter.current_schema_version(_repo("never-initialised", "7"))


# --------------------------------------------------- slice 4: write-side port

_WHASH = "a" * 64


def _adr_rec(
    repository: RepositoryIdentity, adr_id: str = "adr-1"
) -> ADRRecord:
    return ADRRecord(
        repository=repository,
        adr_id=adr_id,
        title="Split payments service",
        status=ADRStatus.APPROVED,
        content_hash=_WHASH,
        decision_id=f"decision-{adr_id}",
        evidence_ids=("ev-1",),
    )


def _decision(repository: RepositoryIdentity) -> ApprovedReviewDecision:
    return ApprovedReviewDecision(
        repository=repository,
        decision_id="decision-x",
        reviewer_id="lead-1",
        adr_draft_id="draft-1",
        adr_draft_content_hash=_WHASH,
        target_fingerprint="fp",
        minted_at=datetime.now(UTC),
    )


def test_upsert_adr_node_persists_and_reopens_with_provenance(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    repo = _repo()
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    adr = _adr_rec(repo)
    node = adapter.upsert_adr_node(repo, adr, _decision(repo))
    assert isinstance(node, NodeId)
    assert node.repository == repo
    assert adapter.write_calls == 1

    # Reopen with a fresh adapter and confirm node + provenance survived.
    reopened = LlamaIndexPropertyGraphAdapter(config=config)
    store = reopened._open_store(repo)
    found = store.get(ids=[adr_node_value(adr)])
    assert len(found) == 1
    assert_complete(found[0].properties)


def test_upsert_rejects_cross_repository_record(tmp_path: Path) -> None:
    config = _config(tmp_path)
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    repo_a = _repo("alpha", "1")
    repo_b = _repo("beta", "2")
    adr_b = _adr_rec(repo_b)
    with pytest.raises(ValueError):
        adapter.upsert_adr_node(repo_a, adr_b, _decision(repo_a))


def test_failed_write_leaves_no_partial_projection(tmp_path: Path) -> None:
    config = _config(tmp_path)
    repo = _repo()
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    adapter.upsert_adr_node(repo, _adr_rec(repo, "adr-1"), _decision(repo))
    writes_before = adapter.write_calls
    # A scope-mismatched record must raise BEFORE mutating the store.
    bad = _adr_rec(_repo("beta", "9"), "adr-2")
    with pytest.raises(ValueError):
        adapter.upsert_adr_node(repo, bad, _decision(repo))
    assert adapter.write_calls == writes_before
    reopened = LlamaIndexPropertyGraphAdapter(config=config)
    ids = {n.id for n in reopened._open_store(repo).get()}
    assert ids == {adr_node_value(_adr_rec(repo, "adr-1"))}


def test_add_relationship_persists_typed_edge(tmp_path: Path) -> None:
    config = _config(tmp_path)
    repo = _repo()
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    adr_node = adapter.upsert_adr_node(repo, _adr_rec(repo, "adr-1"), _decision(repo))
    target = adapter.upsert_adr_node(repo, _adr_rec(repo, "adr-2"), _decision(repo))
    edge = adapter.add_relationship(
        repo, adr_node, target, RelationshipType.ADDRESSES_COMPONENT, _decision(repo)
    )
    assert isinstance(edge, GraphEdge)
    assert edge.relationship == RelationshipType.ADDRESSES_COMPONENT
    reopened = LlamaIndexPropertyGraphAdapter(config=config)
    store = reopened._open_store(repo)
    triplets = store.get_rel_map(store.get(ids=[adr_node.value]), depth=1)
    assert triplets, "relationship did not survive reopen"


def test_record_structural_change_and_supersede_and_retract(tmp_path: Path) -> None:
    config = _config(tmp_path)
    repo = _repo()
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    prior = adapter.upsert_adr_node(repo, _adr_rec(repo, "adr-1"), _decision(repo))
    newer = adapter.upsert_adr_node(repo, _adr_rec(repo, "adr-2"), _decision(repo))
    change = StructuralChange(
        repository=repo,
        change_id="chg-1",
        change_type="dependency_change",
        summary="bump",
        evidence_id="ev-1",
    )
    change_node = adapter.record_structural_change(
        repo, change, prior, _decision(repo)
    )
    assert isinstance(change_node, NodeId)
    sup = adapter.supersede_adr(repo, prior, newer, _decision(repo), "better split")
    assert sup.relationship == RelationshipType.SUPERSEDES
    ret = adapter.retract_adr(repo, newer, _decision(repo), "reverted")
    assert ret.relationship == RelationshipType.RETRACTS


def test_rebuild_snapshot_returns_scoped_ref(tmp_path: Path) -> None:
    config = _config(tmp_path)
    repo = _repo()
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    adapter.upsert_adr_node(repo, _adr_rec(repo), _decision(repo))
    ref = adapter.rebuild_snapshot(repo)
    assert ref.repository == repo
    assert ref.snapshot_id
    assert ref.schema_version == ADAPTER_SCHEMA_VERSION
