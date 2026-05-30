"""Slice 6 tests: workflow-facing schema/API classifier service.

The service runs both detectors over one feature 003 candidate-evidence bundle and
returns a feature-004 :class:`StructuralChangeProducerResult` — the same shape the
dependency producer returns — so feature 008 / 015 consume one producer interface
(US-3, US-6). Schema and API changes in one PR stay distinct, low-confidence
outcomes are retained, and observability is metadata-only.
"""

from __future__ import annotations

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    SCMProviderName,
)
from living_adr.core.structural_change import ADRRecommendation, ChangeType
from living_adr.workflow.classifiers.service import SchemaApiContractClassifier
from living_adr.workflow.structural_change_producer import (
    StructuralChangeProducer,
    StructuralChangeProducerResult,
)

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


class _RecordingObservability:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def record_event(self, name: str, metadata=None) -> None:
        self.events.append((name, dict(metadata or {})))

    def increment_counter(self, name, value=1, metadata=None) -> None:
        return None

    def start_span(self, name, metadata=None):
        from contextlib import nullcontext

        return nullcontext()


def _candidate(*files: ChangedFileMetadata) -> CandidateEvidence:
    return CandidateEvidence(
        repository=REPO,
        source_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        pr_number=42,
        pr_title="Change",
        changed_files=files,
        diff=DiffEvidence(
            diff_handle="github:pulls/42/files", summary="changed files"
        ),
        provider=SCMProviderName.GITHUB,
    )


def test_service_implements_producer_protocol() -> None:
    service = SchemaApiContractClassifier()
    assert isinstance(service, StructuralChangeProducer)


def test_zero_outputs_for_irrelevant_pr() -> None:
    result = SchemaApiContractClassifier().produce(
        _candidate(ChangedFileMetadata(filename="README.md", status="modified",
                                       additions=1))
    )
    assert isinstance(result, StructuralChangeProducerResult)
    assert result.changes == ()
    assert result.no_adr_outcomes == ()


def test_mixed_schema_and_api_pr_emits_distinct_changes() -> None:
    result = SchemaApiContractClassifier().produce(
        _candidate(
            ChangedFileMetadata(filename="db/migrations/0007.sql", status="added",
                                additions=20),
            ChangedFileMetadata(filename="api/openapi.yaml", status="modified",
                                additions=8, deletions=2),
        )
    )
    types = sorted(c.change_type.value for c in result.changes)
    assert types == ["api_contract", "schema"]
    # Distinct records, both draft-eligible.
    assert all(
        c.adr_recommendation is ADRRecommendation.DRAFT for c in result.changes
    )
    assert len(result.draft_eligible_changes) == 2
    assert len(result.evidence) == 2


def test_low_confidence_outcomes_are_retained() -> None:
    result = SchemaApiContractClassifier().produce(
        _candidate(
            ChangedFileMetadata(filename="app/api/dynamic_routes.py",
                                status="modified", additions=4, deletions=2),
        )
    )
    assert result.changes == ()
    assert len(result.no_adr_outcomes) == 1
    assert result.no_adr_outcomes[0].change_type is ChangeType.API_CONTRACT


def test_observability_records_metadata_only() -> None:
    obs = _RecordingObservability()
    SchemaApiContractClassifier(observability=obs).produce(
        _candidate(
            ChangedFileMetadata(filename="db/migrations/0007.sql", status="added",
                                additions=20),
        )
    )
    names = [n for n, _ in obs.events]
    assert any(n.endswith(".started") for n in names)
    assert any(n.endswith(".completed") for n in names)
    completed = next(m for n, m in obs.events if n.endswith(".completed"))
    assert completed["policy_id"] == "semantic-change-default-v1"
    assert completed["change_count"] == 1
    # No raw evidence content leaks into metadata.
    blob = repr(obs.events)
    assert "diff_handle" not in blob
    assert "github:pulls/42/files" not in blob


def test_classifier_error_becomes_diagnostic_not_crash() -> None:
    class _Boom:
        def detect(self, inp):
            raise RuntimeError("boom")

    service = SchemaApiContractClassifier(schema_detector=_Boom())
    result = service.produce(
        _candidate(
            ChangedFileMetadata(filename="db/migrations/0007.sql", status="added",
                                additions=20),
        )
    )
    assert result.changes == ()
    assert any("classification_error" in d for d in result.diagnostics)


def test_produce_is_deterministic() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="db/migrations/0007.sql", status="added",
                            additions=20),
        ChangedFileMetadata(filename="api/openapi.yaml", status="modified",
                            additions=8, deletions=2),
    )
    service = SchemaApiContractClassifier()
    assert service.produce(candidate) == service.produce(candidate)

_ALLOWED_COMPLETED_KEYS = {
    "repository_key",
    "normalized_pr_key",
    "policy_id",
    "change_count",
    "draft_count",
    "no_adr_count",
    "evidence_count",
    "change_types",
    "reason_codes",
    "uncertainty_reasons",
    "max_confidence",
}


def _candidate_with_secret(*files: ChangedFileMetadata) -> CandidateEvidence:
    return CandidateEvidence(
        repository=REPO,
        source_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        pr_number=42,
        pr_title="Change",
        changed_files=files,
        diff=DiffEvidence(
            diff_handle="github:pulls/42/files",
            summary="SECRET_TOKEN_abcdef123 leaked in raw diff body",
        ),
        provider=SCMProviderName.GITHUB,
    )


def test_observability_metadata_excludes_raw_and_secret_content() -> None:
    obs = _RecordingObservability()
    SchemaApiContractClassifier(observability=obs).produce(
        _candidate_with_secret(
            ChangedFileMetadata(filename="db/generated/migrations/0010.sql",
                                status="added", additions=12),
            ChangedFileMetadata(filename="api/openapi.yaml", status="modified",
                                additions=4, deletions=1),
        )
    )
    blob = repr(obs.events)
    # No raw diff body, secret, or diff handle leaks into any event metadata.
    assert "SECRET_TOKEN" not in blob
    assert "raw diff" not in blob
    assert "diff_handle" not in blob
    assert "github:pulls/42/files" not in blob
    completed = next(m for n, m in obs.events if n.endswith(".completed"))
    assert set(completed) <= _ALLOWED_COMPLETED_KEYS
    # Uncertainty surfaced as metadata tokens (generated artifact).
    assert "generated_artifact" in completed["uncertainty_reasons"]


def test_fixture_matrix_direct_generated_mixed_and_no_change() -> None:
    result = SchemaApiContractClassifier().produce(
        _candidate(
            # direct schema
            ChangedFileMetadata(filename="db/migrations/0007.sql", status="added",
                                additions=20),
            # direct api
            ChangedFileMetadata(filename="proto/user.proto", status="modified",
                                additions=6, deletions=2),
            # generated api (uncertain)
            ChangedFileMetadata(filename="api/generated/openapi.json",
                                status="modified", additions=10, deletions=3),
            # dynamic api route (retained, below threshold)
            ChangedFileMetadata(filename="app/api/dynamic_routes.py",
                                status="modified", additions=3, deletions=1),
            # no-change noise
            ChangedFileMetadata(filename="README.md", status="modified",
                                additions=1),
        )
    )
    # Schema and API stay distinct; nothing collapses into a generic bucket.
    schema_changes = [c for c in result.changes
                      if c.change_type is ChangeType.SCHEMA]
    api_changes = [c for c in result.changes
                   if c.change_type is ChangeType.API_CONTRACT]
    assert len(schema_changes) == 1
    assert len(api_changes) >= 1
    # Low-confidence dynamic route retained, never dropped.
    assert any(o.change_type is ChangeType.API_CONTRACT
               for o in result.no_adr_outcomes)
    # Every change links to emitted evidence.
    evidence_ids = {e.id for e in result.evidence}
    for change in result.changes:
        assert set(change.evidence_ids) <= evidence_ids
