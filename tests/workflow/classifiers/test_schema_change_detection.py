"""Slice 3 RED tests: deterministic database/schema change detection.

The schema detector classifies migration / DDL / ORM-model / schema-registry /
validation evidence into ``change_type=schema`` :class:`StructuralChange` records
that reuse the feature 004 serialized field set. Seed/test/comment-only diffs do
not produce high-confidence schema changes, and generated / runtime-limited
evidence carries explicit uncertainty (US-1, US-4).
"""

from __future__ import annotations

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    SCMProviderName,
)
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeType,
    ReasonCode,
)
from living_adr.workflow.classifiers.inputs import (
    UncertaintyReason,
    build_classifier_input,
)
from living_adr.workflow.classifiers.schema import SchemaChangeDetector

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


def _input(*files: ChangedFileMetadata):
    candidate = CandidateEvidence(
        repository=REPO,
        source_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        pr_number=42,
        pr_title="Change",
        changed_files=files,
        diff=DiffEvidence(diff_handle="github:pulls/42/files", summary="changed"),
        provider=SCMProviderName.GITHUB,
    )
    return build_classifier_input(candidate)


def _detect(*files: ChangedFileMetadata):
    return SchemaChangeDetector().detect(_input(*files))


def test_sql_migration_is_draft_eligible_schema_change() -> None:
    outcome = _detect(
        ChangedFileMetadata(
            filename="db/migrations/0007_add_orders.sql",
            status="added",
            additions=40,
        ),
    )
    assert len(outcome.changes) == 1
    change = outcome.changes[0]
    assert change.change_type is ChangeType.SCHEMA
    assert change.adr_recommendation is ADRRecommendation.DRAFT
    assert change.confidence >= 0.70
    assert change.reason_code == ReasonCode.SCHEMA_MIGRATION
    assert change.source_paths == ("db/migrations/0007_add_orders.sql",)
    assert change.classifier_name == "schema-api-contract-change-detection"
    # Evidence is linked and dependency fields stay empty.
    assert change.evidence_ids
    assert change.affected_dependency is None
    assert {e.id for e in outcome.evidence} >= set(change.evidence_ids)


def test_sql_ddl_file_detected() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="sql/schema.sql", status="modified",
                            additions=5, deletions=2),
    )
    (change,) = outcome.changes
    assert change.change_type is ChangeType.SCHEMA
    assert change.reason_code == ReasonCode.SCHEMA_DDL


def test_orm_model_change_detected() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="app/models/order.py", status="modified",
                            additions=6, deletions=1),
    )
    (change,) = outcome.changes
    assert change.change_type is ChangeType.SCHEMA
    assert change.reason_code == ReasonCode.SCHEMA_ORM_MODEL


def test_schema_registry_and_validation_detected() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="schemas/events/order.avsc", status="added",
                            additions=20),
        ChangedFileMetadata(filename="schemas/user.schema.json", status="modified",
                            additions=3, deletions=1),
    )
    reasons = {c.reason_code for c in outcome.changes}
    assert ReasonCode.SCHEMA_REGISTRY in reasons
    assert ReasonCode.SCHEMA_VALIDATION in reasons


def test_seed_and_test_changes_are_not_high_confidence() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="tests/fixtures/seed.sql", status="modified",
                            additions=10, deletions=0),
    )
    # Routed to a retained no-ADR outcome, not a draft-eligible change.
    assert outcome.changes == ()
    assert len(outcome.no_adr_outcomes) == 1
    assert outcome.no_adr_outcomes[0].reason_code == ReasonCode.SEED_OR_TEST_ONLY
    assert outcome.no_adr_outcomes[0].adr_recommendation is (
        ADRRecommendation.NO_ADR_NEEDED
    )


def test_non_schema_files_are_ignored() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="README.md", status="modified", additions=1),
        ChangedFileMetadata(filename="src/util.py", status="modified", additions=2),
    )
    assert outcome.changes == ()
    assert outcome.no_adr_outcomes == ()
    assert outcome.evidence == ()


def test_generated_migration_carries_uncertainty() -> None:
    outcome = _detect(
        ChangedFileMetadata(
            filename="db/generated/migrations/0008_auto.sql",
            status="added",
            additions=30,
        ),
    )
    records = list(outcome.changes) + list(outcome.no_adr_outcomes)
    (record,) = records
    # Uncertainty surfaces through the reason code and the evidence summary.
    assert record.reason_code == ReasonCode.SCHEMA_GENERATED_UNCERTAIN
    (evidence,) = outcome.evidence
    assert UncertaintyReason.GENERATED_ARTIFACT.value in evidence.summary
    assert evidence.provenance["uncertainty"] != "none"


def test_runtime_reflection_orm_carries_uncertainty() -> None:
    outcome = _detect(
        ChangedFileMetadata(
            filename="app/models/dynamic_reflection.py",
            status="modified",
            additions=4,
            deletions=4,
        ),
    )
    (evidence,) = outcome.evidence
    assert UncertaintyReason.RUNTIME_REFLECTION.value in evidence.summary


def test_detection_is_deterministic() -> None:
    files = (
        ChangedFileMetadata(filename="db/migrations/0007.sql", status="added",
                            additions=10),
    )
    detector = SchemaChangeDetector()
    assert detector.detect(_input(*files)) == detector.detect(_input(*files))

def test_comment_only_schema_change_is_retained_no_adr() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="db/migrations/0009.sql", status="modified",
                            additions=0, deletions=0),
    )
    assert outcome.changes == ()
    (record,) = outcome.no_adr_outcomes
    assert record.reason_code == ReasonCode.NO_PERSISTED_SHAPE_CHANGE


def test_ambiguous_extensionless_schema_file_is_ignored() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="docs/schema-notes", status="modified",
                            additions=3, deletions=1),
    )
    assert outcome.changes == ()
