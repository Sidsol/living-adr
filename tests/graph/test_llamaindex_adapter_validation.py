"""Slice 2/3/7 (US-1/US-2/US-4/US-7) — schema metadata, isolation, validation.

Slice 2 covers schema-version metadata governance and repository isolation;
slices 3 and 7 append provenance, label-validation, and drift-diagnostic tests to
this file (they share the validation/diagnostic surface).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from living_adr.core.adr import ADRRecord, ADRStatus
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.approval_bound_mutation import migrate_fingerprint
from living_adr.core.graph.models import (
    MigrationResult,
    SchemaVersion,
    UnsupportedRelationshipError,
)
from living_adr.core.repository import RepositoryIdentity
from living_adr.graph import GraphPersistenceConfig, LlamaIndexPropertyGraphAdapter
from living_adr.graph.persistence import graph_meta_path
from living_adr.graph.schema import (
    ADAPTER_SCHEMA_VERSION,
    SchemaMetadataError,
    UnsupportedEntityLabelError,
    UnsupportedSchemaVersionError,
    validate_entity_label,
    validate_relationship_label,
)

_HASH = "f" * 64


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
        title="Split payments service",
        status=ADRStatus.APPROVED,
        content_hash=_HASH,
        decision_id=f"decision-{adr_id}",
        evidence_ids=("ev-1",),
    )


def _migrate_decision(
    repository: RepositoryIdentity, target: SchemaVersion
) -> ApprovedReviewDecision:
    from datetime import UTC, datetime

    return ApprovedReviewDecision(
        repository=repository,
        decision_id="decision-migrate",
        reviewer_id="lead-1",
        adr_draft_id="draft-1",
        adr_draft_content_hash=_HASH,
        target_fingerprint=migrate_fingerprint(repository, target),
        minted_at=datetime.now(UTC),
    )


# ---------------------------------------------------------- schema metadata


def test_current_schema_version_returns_persisted_value(tmp_path: Path) -> None:
    adapter = LlamaIndexPropertyGraphAdapter(config=_config(tmp_path))
    repo = _repo()
    adapter.initialize_repository(repo)
    assert adapter.current_schema_version(repo) == ADAPTER_SCHEMA_VERSION


def test_missing_metadata_fails_deterministically(tmp_path: Path) -> None:
    adapter = LlamaIndexPropertyGraphAdapter(config=_config(tmp_path))
    with pytest.raises(SchemaMetadataError):
        adapter.current_schema_version(_repo("uninit", "1"))


def test_unsupported_persisted_version_is_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path)
    repo = _repo()
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    adapter.initialize_repository(repo)
    # Tamper the persisted metadata to declare a future, unsupported version.
    meta_path = graph_meta_path(config, repo)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["schema_version"] = {"major": 9, "minor": 9}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    reopened = LlamaIndexPropertyGraphAdapter(config=config)
    with pytest.raises(UnsupportedSchemaVersionError):
        reopened.current_schema_version(repo)


def test_migrate_schema_returns_typed_result_and_persists(tmp_path: Path) -> None:
    config = _config(tmp_path)
    repo = _repo()
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    adapter.initialize_repository(repo)
    target = SchemaVersion(major=2, minor=0)
    result = adapter.migrate_schema(repo, target, _migrate_decision(repo, target))
    assert isinstance(result, MigrationResult)
    assert result.from_version == ADAPTER_SCHEMA_VERSION
    assert result.to_version == target
    assert result.applied is True
    # A fresh adapter sees the migrated version persisted on disk.
    reopened = LlamaIndexPropertyGraphAdapter(config=config)
    meta = json.loads(graph_meta_path(config, repo).read_text(encoding="utf-8"))
    assert meta["schema_version"] == {"major": 2, "minor": 0}
    assert reopened._read_meta(repo)["schema_version"]["major"] == 2


def test_migrate_schema_on_uninitialised_repo_initialises(tmp_path: Path) -> None:
    config = _config(tmp_path)
    repo = _repo("fresh", "7")
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    target = SchemaVersion(major=2, minor=0)
    result = adapter.migrate_schema(repo, target, _migrate_decision(repo, target))
    assert result.to_version == target
    assert adapter.is_initialized(repo) is True


# ---------------------------------------------------------- repository scope


def test_identical_identifiers_in_two_repositories_stay_isolated(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    adapter = LlamaIndexPropertyGraphAdapter(config=config)
    repo_a = _repo("alpha", "1")
    repo_b = _repo("alpha", "2")  # same key text, different opaque id
    adapter.initialize_repository(repo_a)
    adapter.initialize_repository(repo_b)
    # Migrating A's schema must not change B's persisted version.
    target = SchemaVersion(major=2, minor=0)
    adapter.migrate_schema(repo_a, target, _migrate_decision(repo_a, target))
    meta_a = adapter._read_meta(repo_a)
    assert meta_a["schema_version"] == {"major": 2, "minor": 0}
    assert adapter.current_schema_version(repo_b) == ADAPTER_SCHEMA_VERSION


# ---------------------------------------------------------- label validation


def test_validate_relationship_label_accepts_known_and_rejects_unknown() -> None:
    assert validate_relationship_label("supersedes").value == "supersedes"
    with pytest.raises(UnsupportedRelationshipError):
        validate_relationship_label("totally-made-up")


def test_validate_entity_label_accepts_known_and_rejects_unknown() -> None:
    assert validate_entity_label("adr") == "adr"
    with pytest.raises(UnsupportedEntityLabelError):
        validate_entity_label("not-a-real-label")
