"""Slice 2/3/7 (US-1/US-2/US-4/US-7) — schema metadata, isolation, validation.

Slice 2 covers schema-version metadata governance and repository isolation;
slices 3 and 7 append provenance, label-validation, and drift-diagnostic tests to
this file (they share the validation/diagnostic surface).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from living_adr.core.adr import ADRRecord, ADRStatus
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.approval_bound_mutation import migrate_fingerprint
from living_adr.core.graph.models import (
    GraphEdge,
    MigrationResult,
    NodeId,
    RelationshipType,
    SchemaVersion,
    UnsupportedRelationshipError,
)
from living_adr.core.repository import RepositoryIdentity
from living_adr.graph import GraphPersistenceConfig, LlamaIndexPropertyGraphAdapter
from living_adr.graph.llamaindex_mapping import (
    ADR_ID_KEY,
    NODE_KIND_KEY,
    SCOPE_KEY_PROP,
    MappingValidationError,
    adr_to_entity_node,
    edge_to_relation,
    validate_extracted_triple,
)
from living_adr.graph.persistence import graph_meta_path
from living_adr.graph.provenance import (
    PROV_DECISION_ID,
    PROV_SCOPE_KEY,
    EntityProvenance,
    ExtractionMethod,
    MissingProvenanceError,
    ProvenanceRepositoryMismatchError,
    assert_complete,
    assert_scope,
    provenance_from_properties,
    provenance_to_properties,
    scope_key,
)
from living_adr.graph.schema import (
    ADAPTER_NAME,
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


# ----------------------------------------------------- slice 3: provenance


def _prov(repository: RepositoryIdentity, adr_id: str = "adr-1") -> EntityProvenance:
    return EntityProvenance(
        repository=repository,
        source_adr_id=adr_id,
        decision_id=f"decision-{adr_id}",
        extraction_method=ExtractionMethod.DETERMINISTIC_ADR_PROJECTION,
        extracted_at=datetime.now(UTC),
        schema_version=ADAPTER_SCHEMA_VERSION,
        evidence_id="ev-1",
    )


def test_provenance_roundtrips_through_properties() -> None:
    repo = _repo()
    prov = _prov(repo)
    props = provenance_to_properties(prov)
    assert props[PROV_SCOPE_KEY] == scope_key(repo)
    restored = provenance_from_properties(repo, props)
    assert restored.source_adr_id == prov.source_adr_id
    assert restored.decision_id == prov.decision_id
    assert restored.extraction_method == prov.extraction_method
    assert restored.schema_version == prov.schema_version


def test_incomplete_provenance_is_rejected() -> None:
    repo = _repo()
    props = provenance_to_properties(_prov(repo))
    del props[PROV_DECISION_ID]
    with pytest.raises(MissingProvenanceError):
        assert_complete(props)


def test_empty_provenance_value_is_rejected() -> None:
    repo = _repo()
    props = provenance_to_properties(_prov(repo))
    props[PROV_DECISION_ID] = "   "
    with pytest.raises(MissingProvenanceError):
        assert_complete(props)


def test_provenance_repository_mismatch_detected() -> None:
    repo_a = _repo("alpha", "1")
    repo_b = _repo("beta", "2")
    props = provenance_to_properties(_prov(repo_a))
    assert_scope(repo_a, props)  # matching scope is fine
    with pytest.raises(ProvenanceRepositoryMismatchError):
        assert_scope(repo_b, props)


def test_adr_entity_node_carries_provenance_and_scope() -> None:
    repo = _repo()
    adr = _adr(repo)
    node = adr_to_entity_node(repo, adr, _prov(repo, adr.adr_id))
    assert node.properties[SCOPE_KEY_PROP] == scope_key(repo)
    assert node.properties[ADR_ID_KEY] == adr.adr_id
    # Provenance must be present so the node can be cited/audited.
    assert_complete(node.properties)


def test_edge_relation_uses_validated_label_and_provenance() -> None:
    repo = _repo()
    from_node = NodeId(repository=repo, value="adr:adr-1")
    to_node = NodeId(repository=repo, value="component:payments")
    edge = GraphEdge(
        repository=repo,
        from_node=from_node,
        to_node=to_node,
        relationship=RelationshipType.ADDRESSES_COMPONENT,
    )
    relation = edge_to_relation(edge, _prov(repo))
    assert relation.label == "addresses_component"
    assert relation.source_id == "adr:adr-1"
    assert_complete(relation.properties)


def test_unsupported_extracted_triple_is_quarantined() -> None:
    # A made-up relationship label from an unconstrained extractor is rejected.
    with pytest.raises(MappingValidationError):
        validate_extracted_triple("adr", "totally-made-up", "component")
    # A made-up entity label is rejected too.
    with pytest.raises(MappingValidationError):
        validate_extracted_triple("adr", "addresses_component", "not-a-label")
    # A fully valid triple maps cleanly.
    validate_extracted_triple("adr", "addresses_component", "component")


# ------------------------------------------------ slice 7: drift diagnostics


def _wdecision(repository: RepositoryIdentity) -> ApprovedReviewDecision:
    return ApprovedReviewDecision(
        repository=repository,
        decision_id="decision-x",
        reviewer_id="lead-1",
        adr_draft_id="draft-1",
        adr_draft_content_hash=_HASH,
        target_fingerprint="fp",
        minted_at=datetime.now(UTC),
    )


def test_check_conformance_passes_for_clean_graph(tmp_path: Path) -> None:
    adapter = LlamaIndexPropertyGraphAdapter(config=_config(tmp_path))
    repo = _repo()
    adapter.initialize_repository(repo)
    a1 = adapter.upsert_adr_node(repo, _adr(repo, "adr-1"), _wdecision(repo))
    a2 = adapter.upsert_adr_node(repo, _adr(repo, "adr-2"), _wdecision(repo))
    adapter.add_relationship(
        repo, a2, a1, RelationshipType.SUPERSEDES, _wdecision(repo)
    )
    report = adapter.check_conformance(repo)
    assert report.adapter_name == ADAPTER_NAME
    assert report.repository == repo
    assert report.ok is True
    assert report.violations == ()


def test_check_conformance_reports_missing_metadata(tmp_path: Path) -> None:
    adapter = LlamaIndexPropertyGraphAdapter(config=_config(tmp_path))
    report = adapter.check_conformance(_repo())
    assert report.ok is False
    assert any("missing_schema_metadata" in v for v in report.violations)


def test_check_conformance_reports_orphan_and_missing_provenance(
    tmp_path: Path,
) -> None:
    adapter = LlamaIndexPropertyGraphAdapter(config=_config(tmp_path))
    repo = _repo()
    adapter.initialize_repository(repo)
    a1 = adapter.upsert_adr_node(repo, _adr(repo, "adr-1"), _wdecision(repo))
    ghost = NodeId(repository=repo, value="component:ghost")
    adapter.add_relationship(
        repo, a1, ghost, RelationshipType.ADDRESSES_COMPONENT, _wdecision(repo)
    )
    report = adapter.check_conformance(repo)
    assert report.ok is False
    assert any(v.startswith("orphan_edge") for v in report.violations)
    assert any(v.startswith("missing_provenance") for v in report.violations)


def test_check_conformance_reports_unsupported_schema_version(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    repo = _repo()
    LlamaIndexPropertyGraphAdapter(config=config).initialize_repository(repo)
    meta_path = graph_meta_path(config, repo)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["schema_version"] = {"major": 9, "minor": 9}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    # Fresh adapter so no cached metadata is served from the prior instance.
    report = LlamaIndexPropertyGraphAdapter(config=config).check_conformance(repo)
    assert report.ok is False
    assert any("unsupported_schema_version" in v for v in report.violations)


def test_check_conformance_reports_repository_mismatch(tmp_path: Path) -> None:
    from llama_index.core.graph_stores.types import EntityNode

    adapter = LlamaIndexPropertyGraphAdapter(config=_config(tmp_path))
    repo = _repo()
    adapter.initialize_repository(repo)
    adapter.upsert_adr_node(repo, _adr(repo, "adr-1"), _wdecision(repo))
    # Inject a fully-provenanced node that belongs to a *different* repository.
    other = _repo(repo="beta", repo_id="999")
    foreign_prov = EntityProvenance(
        repository=other,
        source_adr_id="adr-x",
        decision_id="decision-x",
        extraction_method=ExtractionMethod.DETERMINISTIC_ADR_PROJECTION,
        extracted_at=datetime.now(UTC),
        schema_version=ADAPTER_SCHEMA_VERSION,
    )
    props = provenance_to_properties(foreign_prov)
    props[NODE_KIND_KEY] = "adr"
    props[SCOPE_KEY_PROP] = scope_key(other)
    props[ADR_ID_KEY] = "adr-x"
    store = adapter._open_store(repo)
    store.upsert_nodes([EntityNode(label="adr", name="adr:adr-x", properties=props)])
    adapter._persist_store(repo)
    report = adapter.check_conformance(repo)
    assert report.ok is False
    assert any(v.startswith("repository_mismatch") for v in report.violations)
