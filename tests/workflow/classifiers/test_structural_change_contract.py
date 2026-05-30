"""Slice 1 RED tests: schema/API reuse feature 004's serialized contract.

Feature 005 must emit ``StructuralChange`` / ``ChangeEvidence`` records whose
serialized field set is *byte-identical* to feature 004 (same keys, same shapes),
carrying schema/API semantics only through existing fields and widened enum
values. These tests pin that reuse so a future drift from feature 004 fails fast.
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
    ReasonCode,
    StructuralChange,
    build_evidence_id,
    build_structural_change_id,
    compute_evidence_hash,
)

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)
EVENT = "github:github.com/acme/widgets:42:mergesha"

# The exact feature 004 serialized field sets, pinned here as the contract.
STRUCTURAL_CHANGE_KEYS = {
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
}
EVIDENCE_KEYS = {
    "id",
    "repository",
    "source_scm_event_id",
    "provider_delivery_id",
    "normalized_pr_key",
    "evidence_kind",
    "source_path",
    "diff_hunk_ref",
    "before_value",
    "after_value",
    "observed_operation",
    "parser",
    "parser_version",
    "immutable_hash",
    "summary",
    "provenance",
}


def _change(change_type: ChangeType, source_path: str) -> StructuralChange:
    return StructuralChange(
        id=build_structural_change_id(
            repository=REPO,
            source_scm_event_id=EVENT,
            change_type=change_type,
            operation=ChangeOperation.MODIFIED,
            affected_dependency=None,
            source_paths=(source_path,),
        ),
        repository=REPO,
        source_scm_event_id=EVENT,
        provider_delivery_id="d-1",
        normalized_pr_key=EVENT,
        change_type=change_type,
        operation=ChangeOperation.MODIFIED,
        affected_dependency=None,
        dependency_ecosystem=None,
        source_paths=(source_path,),
        evidence_ids=("ev-1",),
        confidence=0.85,
        reason_code=ReasonCode.SCHEMA_MIGRATION,
        adr_recommendation=ADRRecommendation.DRAFT,
        classifier_name="schema-api-contract-change-detection",
        classifier_version="1.0.0",
    )


def _evidence(kind: EvidenceKind, source_path: str) -> ChangeEvidence:
    return ChangeEvidence(
        id=build_evidence_id(
            repository=REPO,
            source_scm_event_id=EVENT,
            source_path=source_path,
            evidence_kind=kind,
        ),
        repository=REPO,
        source_scm_event_id=EVENT,
        provider_delivery_id="d-1",
        normalized_pr_key=EVENT,
        evidence_kind=kind,
        source_path=source_path,
        diff_hunk_ref=f"github:pulls/42/files#{source_path}",
        before_value=None,
        after_value=None,
        observed_operation=ChangeOperation.MODIFIED.value,  # widened value reuse
        parser="living-adr-schema-evidence",
        parser_version="1.0.0",
        immutable_hash=compute_evidence_hash(
            repository=REPO,
            source_scm_event_id=EVENT,
            source_path=source_path,
            evidence_kind=kind,
            before_value=None,
            after_value=None,
        ),
        summary=f"{source_path}: schema migration; confidence=0.85",
        provenance={"policy_id": "semantic-change-default-v1"},
    )


def test_change_type_enum_widened_for_schema_and_api() -> None:
    assert ChangeType.SCHEMA.value == "schema"
    assert ChangeType.API_CONTRACT.value == "api_contract"
    # Dependency value is untouched (byte-identical with feature 004).
    assert ChangeType.DEPENDENCY.value == "dependency"


def test_schema_change_uses_feature004_serialized_field_set() -> None:
    schema = _change(ChangeType.SCHEMA, "db/migrations/0007_add_orders.sql")
    api = _change(ChangeType.API_CONTRACT, "api/openapi.yaml")
    schema_keys = set(schema.model_dump(mode="json").keys())
    api_keys = set(api.model_dump(mode="json").keys())
    assert schema_keys == STRUCTURAL_CHANGE_KEYS
    assert api_keys == STRUCTURAL_CHANGE_KEYS
    assert schema.model_dump(mode="json")["change_type"] == "schema"
    assert api.model_dump(mode="json")["change_type"] == "api_contract"
    # Dependency-specific fields remain present but unused.
    assert schema.affected_dependency is None
    assert schema.dependency_ecosystem is None


def test_schema_evidence_uses_feature004_serialized_field_set() -> None:
    ev = _evidence(EvidenceKind.SCHEMA_MIGRATION, "db/migrations/0007.sql")
    assert set(ev.model_dump(mode="json").keys()) == EVIDENCE_KEYS
    assert ev.model_dump(mode="json")["evidence_kind"] == "schema_migration"


def test_widened_evidence_kinds_present() -> None:
    for kind in (
        EvidenceKind.SCHEMA_MIGRATION,
        EvidenceKind.SCHEMA_DDL,
        EvidenceKind.SCHEMA_ORM_MODEL,
        EvidenceKind.SCHEMA_REGISTRY,
        EvidenceKind.SCHEMA_VALIDATION,
        EvidenceKind.API_OPENAPI,
        EvidenceKind.API_GRAPHQL,
        EvidenceKind.API_PROTOBUF,
        EvidenceKind.API_ROUTE,
        EvidenceKind.API_MODEL,
    ):
        assert isinstance(kind.value, str)


def test_confidence_still_bounded_for_schema_changes() -> None:
    with pytest.raises(ValueError):
        StructuralChange(
            id="x",
            repository=REPO,
            source_scm_event_id=EVENT,
            provider_delivery_id="d-1",
            normalized_pr_key=EVENT,
            change_type=ChangeType.SCHEMA,
            operation=ChangeOperation.MODIFIED,
            affected_dependency=None,
            dependency_ecosystem=None,
            source_paths=("x.sql",),
            evidence_ids=("ev-1",),
            confidence=1.5,
            reason_code=ReasonCode.SCHEMA_MIGRATION,
            adr_recommendation=ADRRecommendation.DRAFT,
            classifier_name="schema-api-contract-change-detection",
            classifier_version="1.0.0",
        )


def test_low_confidence_evidence_is_retained_not_dropped() -> None:
    # A below-threshold schema candidate is still a valid evidence record.
    ev = _evidence(EvidenceKind.SCHEMA_VALIDATION, "schemas/user.schema.json")
    assert ev.immutable_hash
    assert ev.summary
