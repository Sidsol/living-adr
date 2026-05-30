"""Slice S-001 RED tests: the cross-feature structural-change contract.

Feature 004 defines the first production ``StructuralChange`` / ``ChangeEvidence``
contract. Features 005 (schema/API classifiers) and 008 (Claude drafting) bind to
*these exact shapes*, so the fields, enums, stable-id formula, and serialization
are pinned here. Determinism is a hard requirement (NFR-1): identical inputs must
produce identical ids, hashes, and serialized output.
"""

from __future__ import annotations

import pytest

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeEvidence,
    ChangeOperation,
    ChangeType,
    EvidenceKind,
    NoAdrOutcome,
    ObservedOperation,
    ReasonCode,
    StructuralChange,
    build_evidence_id,
    build_structural_change_id,
    compute_evidence_hash,
)

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


def _evidence(**overrides: object) -> ChangeEvidence:
    base: dict[str, object] = dict(
        repository=REPO,
        source_scm_event_id="github:github.com/acme/widgets:42:mergesha",
        provider_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        evidence_kind=EvidenceKind.DEPENDENCY_MANIFEST,
        source_path="package.json",
        diff_hunk_ref="github:pulls/42/files#package.json",
        before_value=None,
        after_value="httpx@^0.27",
        observed_operation=ObservedOperation.ADDED,
        parser="living-adr-dependency-evidence",
        parser_version="1.0.0",
        summary="package.json: 1 dependency added",
        provenance={"source_delivery_id": "d-1"},
    )
    base.update(overrides)
    path = str(base["source_path"])
    base["immutable_hash"] = compute_evidence_hash(
        repository=REPO,
        source_scm_event_id=str(base["source_scm_event_id"]),
        source_path=path,
        evidence_kind=EvidenceKind(base["evidence_kind"]),
        before_value=base["before_value"],  # type: ignore[arg-type]
        after_value=base["after_value"],  # type: ignore[arg-type]
    )
    base["id"] = build_evidence_id(
        repository=REPO,
        source_scm_event_id=str(base["source_scm_event_id"]),
        source_path=path,
        evidence_kind=EvidenceKind(base["evidence_kind"]),
    )
    return ChangeEvidence(**base)  # type: ignore[arg-type]


def test_change_evidence_carries_full_contract_and_is_immutable() -> None:
    evidence = _evidence()
    assert evidence.repository == REPO
    assert evidence.source_scm_event_id.endswith(":42:mergesha")
    assert evidence.provider_delivery_id == "d-1"
    assert evidence.evidence_kind is EvidenceKind.DEPENDENCY_MANIFEST
    assert evidence.source_path == "package.json"
    assert evidence.observed_operation is ObservedOperation.ADDED
    assert evidence.parser_version == "1.0.0"
    assert evidence.immutable_hash  # non-empty deterministic hash
    assert evidence.summary
    assert evidence.provenance["source_delivery_id"] == "d-1"
    with pytest.raises((TypeError, ValueError, AttributeError)):
        evidence.source_path = "tampered"  # type: ignore[misc]


def test_evidence_id_and_hash_are_deterministic() -> None:
    first = _evidence()
    second = _evidence()
    assert first.id == second.id
    assert first.immutable_hash == second.immutable_hash
    # Different source path -> different id and hash.
    other = _evidence(source_path="package-lock.json")
    assert other.id != first.id


def test_evidence_hash_changes_with_observed_values() -> None:
    base = _evidence()
    changed = _evidence(before_value="httpx@^0.26", after_value="httpx@^0.27")
    assert changed.immutable_hash != base.immutable_hash


def _change(**overrides: object) -> StructuralChange:
    base: dict[str, object] = dict(
        repository=REPO,
        source_scm_event_id="github:github.com/acme/widgets:42:mergesha",
        provider_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        change_type=ChangeType.DEPENDENCY,
        operation=ChangeOperation.ADDED,
        affected_dependency="httpx",
        dependency_ecosystem="npm",
        source_paths=("package.json",),
        evidence_ids=("ev-1",),
        confidence=0.8,
        reason_code=ReasonCode.DIRECT_MANIFEST_ADD,
        adr_recommendation=ADRRecommendation.DRAFT,
        classifier_name="dependency-change",
        classifier_version="1.0.0",
    )
    base.update(overrides)
    base["id"] = build_structural_change_id(
        repository=REPO,
        source_scm_event_id=str(base["source_scm_event_id"]),
        change_type=ChangeType(base["change_type"]),
        operation=ChangeOperation(base["operation"]),
        affected_dependency=base["affected_dependency"],  # type: ignore[arg-type]
        source_paths=tuple(base["source_paths"]),  # type: ignore[arg-type]
    )
    return StructuralChange(**base)  # type: ignore[arg-type]


def test_structural_change_serializes_full_contract() -> None:
    change = _change()
    dumped = change.model_dump(mode="json")
    for key in (
        "id",
        "repository",
        "source_scm_event_id",
        "provider_delivery_id",
        "normalized_pr_key",
        "change_type",
        "operation",
        "affected_dependency",
        "dependency_ecosystem",
        "source_paths",
        "evidence_ids",
        "confidence",
        "reason_code",
        "adr_recommendation",
        "classifier_name",
        "classifier_version",
    ):
        assert key in dumped
    assert dumped["change_type"] == "dependency"
    assert dumped["operation"] == "added"
    assert dumped["adr_recommendation"] == "draft"
    assert dumped["source_paths"] == ["package.json"]


def test_structural_change_id_is_deterministic_and_path_sensitive() -> None:
    assert _change().id == _change().id
    assert _change(source_paths=("pyproject.toml",)).id != _change().id
    assert _change(operation=ChangeOperation.REMOVED).id != _change().id


def test_structural_change_is_immutable() -> None:
    change = _change()
    with pytest.raises((TypeError, ValueError, AttributeError)):
        change.confidence = 0.1  # type: ignore[misc]


def test_confidence_must_be_within_unit_interval() -> None:
    with pytest.raises(ValueError):
        _change(confidence=1.5)
    with pytest.raises(ValueError):
        _change(confidence=-0.1)


def test_no_adr_outcome_contract() -> None:
    outcome = NoAdrOutcome(
        id="outcome-1",
        repository=REPO,
        source_scm_event_id="github:github.com/acme/widgets:42:mergesha",
        provider_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        change_type=ChangeType.DEPENDENCY,
        reason_code=ReasonCode.LOCKFILE_ONLY,
        confidence=0.3,
        source_paths=("package-lock.json",),
        evidence_ids=("ev-1",),
    )
    assert outcome.adr_recommendation is ADRRecommendation.NO_ADR_NEEDED
    assert outcome.reason_code == "lockfile_only_churn"
    assert outcome.model_dump(mode="json")["adr_recommendation"] == "no_adr_needed"
    with pytest.raises((TypeError, ValueError, AttributeError)):
        outcome.confidence = 0.9  # type: ignore[misc]
