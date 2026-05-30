"""Slice 1 (US-1/US-3) — persistence root, path derivation, reopen, no leakage.

These tests pin the adapter's local persistence contract before any graph
behaviour exists: deterministic repository-partitioned paths under ``var\\graph``,
path-traversal safety, initialize/reopen semantics, and the rule that no public
attribute exposes a LlamaIndex storage context or SQLite connection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from living_adr.core.repository import RepositoryIdentity
from living_adr.graph import GraphPersistenceConfig, LlamaIndexPropertyGraphAdapter
from living_adr.graph.persistence import (
    OpenMode,
    repository_storage_dir,
)
from living_adr.graph.schema import SchemaMetadataError


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
