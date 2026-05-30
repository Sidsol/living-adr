"""Slice S-005 RED tests: dependency change producer facade + replay + telemetry.

The producer is the first :class:`StructuralChangeProducer`. It consumes Feature
003 candidate evidence and returns one typed result holding draft-eligible changes
and no-ADR outcomes, deterministically (replay-stable), while emitting only
metadata-only observability events and converting unexpected classifier failures
into typed diagnostics instead of crashing the workflow.
"""

from __future__ import annotations

from living_adr.core.observability import Metadata
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    SCMProviderName,
)
from living_adr.workflow.dependency_change_producer import DependencyChangeProducer
from living_adr.workflow.structural_change_producer import (
    StructuralChangeProducer,
    StructuralChangeProducerResult,
)

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


def _candidate(*files: ChangedFileMetadata) -> CandidateEvidence:
    return CandidateEvidence(
        repository=REPO,
        source_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        pr_number=42,
        pr_title="Update deps",
        changed_files=files,
        diff=DiffEvidence(diff_handle="github:pulls/42/files", summary="changed"),
        provider=SCMProviderName.GITHUB,
    )


class RecordingObservability:
    """Metadata-only fake that records emitted event names + metadata."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def record_event(self, name: str, metadata: Metadata = None) -> None:
        self.events.append((name, dict(metadata or {})))

    def increment_counter(
        self, name: str, value: int = 1, metadata: Metadata = None
    ) -> None:
        self.events.append((name, dict(metadata or {})))

    def start_span(self, name: str, metadata: Metadata = None):  # pragma: no cover
        raise NotImplementedError


def test_producer_implements_protocol() -> None:
    assert isinstance(DependencyChangeProducer(), StructuralChangeProducer)


def test_producer_returns_typed_result_with_changes_and_outcomes() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
        ChangedFileMetadata(
            filename="poetry.lock", status="modified", additions=30, deletions=4
        ),
    )
    result = DependencyChangeProducer().produce(candidate)
    assert isinstance(result, StructuralChangeProducerResult)
    assert len(result.changes) == 1
    assert len(result.no_adr_outcomes) == 1
    assert result.draft_eligible_changes == result.changes
    assert result.evidence  # supporting immutable evidence carried through


def test_producer_output_is_replay_stable() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
        ChangedFileMetadata(
            filename="package-lock.json", status="modified", additions=50
        ),
    )
    producer = DependencyChangeProducer()
    first = producer.produce(candidate)
    second = producer.produce(candidate)
    assert first.model_dump_json() == second.model_dump_json()


def test_producer_emits_metadata_only_telemetry() -> None:
    obs = RecordingObservability()
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
    )
    DependencyChangeProducer(observability=obs).produce(candidate)
    names = [name for name, _ in obs.events]
    assert "dependency_classification.started" in names
    assert "dependency_classification.completed" in names
    completed = next(m for n, m in obs.events if n.endswith("completed"))
    assert completed["repository_key"] == REPO.key
    assert completed["draft_count"] == 1


class _BoomClassifier:
    def classify(self, candidate: object):
        raise RuntimeError("boom")


def test_producer_converts_classifier_failure_to_diagnostics() -> None:
    obs = RecordingObservability()
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
    )
    producer = DependencyChangeProducer(classifier=_BoomClassifier(), observability=obs)
    result = producer.produce(candidate)  # must not raise
    assert result.changes == ()
    assert result.no_adr_outcomes == ()
    assert any("RuntimeError" in d for d in result.diagnostics)
    assert any(n.endswith("error") for n, _ in obs.events)
