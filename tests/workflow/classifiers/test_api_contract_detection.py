"""Slice 4 RED tests: deterministic API-contract change detection.

The API detector classifies OpenAPI / GraphQL / protobuf / route-signature /
request-response-model / status-error evidence into ``change_type=api_contract``
records reusing the feature 004 serialized field set. Internal implementation-only
handler changes are not high-confidence contract changes, and generated / dynamic
routing evidence carries explicit uncertainty (US-2, US-4).
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
from living_adr.workflow.classifiers.api_contract import APIContractChangeDetector
from living_adr.workflow.classifiers.inputs import (
    UncertaintyReason,
    build_classifier_input,
)

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
    return APIContractChangeDetector().detect(_input(*files))


def test_openapi_spec_is_draft_eligible_api_change() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="api/openapi.yaml", status="modified",
                            additions=12, deletions=3),
    )
    (change,) = outcome.changes
    assert change.change_type is ChangeType.API_CONTRACT
    assert change.adr_recommendation is ADRRecommendation.DRAFT
    assert change.confidence >= 0.70
    assert change.reason_code == ReasonCode.API_OPENAPI_CONTRACT
    assert change.classifier_name == "schema-api-contract-change-detection"
    assert change.affected_dependency is None
    assert {e.id for e in outcome.evidence} >= set(change.evidence_ids)


def test_graphql_schema_detected() -> None:
    (change,) = _detect(
        ChangedFileMetadata(filename="graph/schema.graphql", status="modified",
                            additions=4, deletions=1),
    ).changes
    assert change.reason_code == ReasonCode.API_GRAPHQL_CONTRACT


def test_protobuf_detected() -> None:
    (change,) = _detect(
        ChangedFileMetadata(filename="proto/user.proto", status="modified",
                            additions=6),
    ).changes
    assert change.reason_code == ReasonCode.API_PROTOBUF_CONTRACT
    assert change.change_type is ChangeType.API_CONTRACT


def test_route_signature_detected() -> None:
    (change,) = _detect(
        ChangedFileMetadata(filename="app/api/routes.py", status="modified",
                            additions=8, deletions=2),
    ).changes
    assert change.reason_code == ReasonCode.API_ROUTE_SIGNATURE


def test_request_response_model_detected() -> None:
    (change,) = _detect(
        ChangedFileMetadata(filename="app/api/serializers.py", status="modified",
                            additions=5, deletions=1),
    ).changes
    assert change.reason_code == ReasonCode.API_REQUEST_RESPONSE_MODEL


def test_status_error_semantics_detected() -> None:
    (change,) = _detect(
        ChangedFileMetadata(filename="app/api/errors.py", status="modified",
                            additions=3, deletions=1),
    ).changes
    assert change.reason_code == ReasonCode.API_STATUS_ERROR


def test_internal_handler_is_not_high_confidence() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="app/api/internal/user_handler.py",
                            status="modified", additions=10, deletions=4),
    )
    assert outcome.changes == ()


def test_generated_api_artifact_carries_uncertainty() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="app/api/generated/openapi.json",
                            status="modified", additions=20, deletions=5),
    )
    records = list(outcome.changes) + list(outcome.no_adr_outcomes)
    (record,) = records
    assert record.reason_code == ReasonCode.API_GENERATED_UNCERTAIN
    (evidence,) = outcome.evidence
    assert UncertaintyReason.GENERATED_ARTIFACT.value in evidence.summary


def test_dynamic_route_carries_uncertainty_and_is_retained() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="app/api/dynamic_routes.py",
                            status="modified", additions=6, deletions=2),
    )
    # Below threshold once the dynamic-routing penalty is applied: retained.
    assert outcome.changes == ()
    (outcome_record,) = outcome.no_adr_outcomes
    assert outcome_record.reason_code == ReasonCode.API_DYNAMIC_ROUTE_UNCERTAIN
    (evidence,) = outcome.evidence
    assert UncertaintyReason.DYNAMIC_ROUTING.value in evidence.summary


def test_non_api_files_are_ignored() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="README.md", status="modified", additions=1),
        ChangedFileMetadata(filename="src/util.py", status="modified", additions=2),
    )
    assert outcome.changes == ()
    assert outcome.no_adr_outcomes == ()
    assert outcome.evidence == ()


def test_detection_is_deterministic() -> None:
    files = (
        ChangedFileMetadata(filename="api/openapi.yaml", status="modified",
                            additions=3, deletions=1),
    )
    detector = APIContractChangeDetector()
    assert detector.detect(_input(*files)) == detector.detect(_input(*files))

def test_comment_only_api_change_is_retained_no_adr() -> None:
    outcome = _detect(
        ChangedFileMetadata(filename="api/openapi.yaml", status="modified",
                            additions=0, deletions=0),
    )
    assert outcome.changes == ()
    (record,) = outcome.no_adr_outcomes
    assert record.reason_code == ReasonCode.NO_PERSISTED_SHAPE_CHANGE
