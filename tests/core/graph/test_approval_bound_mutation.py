"""Slice 4 (US-4) tests: ApprovalBoundMutationService is the only write path.

The service must reject every invalid approval *before* touching the graph
adapter (zero adapter calls), and must delegate exactly once for a valid
approved decision while emitting only metadata-only observability. This is the
safety-critical boundary that makes unapproved authoritative mutation
constructively impossible (architecture #service-boundaries; SM-05; FM-13).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from living_adr.core.adr import ADRRecord, ADRStatus
from living_adr.core.approval import (
    ApprovalRequiredError,
    ApprovedReviewDecision,
    DecisionAlreadyConsumedError,
    DecisionRepositoryMismatchError,
    DraftContentMismatchError,
    MutationFingerprintMismatchError,
)
from living_adr.core.graph.approval_bound_mutation import (
    ApprovalBoundMutationService,
    migrate_fingerprint,
    relationship_fingerprint,
    upsert_fingerprint,
)
from living_adr.core.graph.models import (
    GraphEdge,
    MigrationResult,
    NodeId,
    RelationshipType,
    SchemaVersion,
)
from living_adr.core.repository import RepositoryIdentity

CONTENT_HASH = "c" * 64


def repo(name: str = "alpha") -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo=name, repo_id="42"
    )


def adr_record(repository: RepositoryIdentity | None = None) -> ADRRecord:
    return ADRRecord(
        repository=repository or repo(),
        adr_id="adr-1",
        title="Split payments",
        status=ADRStatus.APPROVED,
        content_hash=CONTENT_HASH,
        decision_id="decision-1",
        markdown="# secret rationale body that must never be exported",
    )


def decision(
    repository: RepositoryIdentity,
    fingerprint: str,
    *,
    approved: bool = True,
    content_hash: str = CONTENT_HASH,
    decision_id: str = "decision-1",
) -> ApprovedReviewDecision:
    return ApprovedReviewDecision(
        repository=repository,
        decision_id=decision_id,
        reviewer_id="lead-1",
        adr_draft_id="draft-1",
        adr_draft_content_hash=content_hash,
        target_fingerprint=fingerprint,
        minted_at=datetime.now(UTC),
        approved=approved,
    )


class RecordingStore:
    """Counting ``ArchitectureGraphStore`` double for adapter-call assertions."""

    def __init__(self) -> None:
        self.calls = 0

    def upsert_adr_node(self, repository, adr, decision) -> NodeId:  # noqa: ANN001
        self.calls += 1
        return NodeId(repository=repository, value=f"node-{adr.adr_id}")

    def add_relationship(
        self, repository, from_node, to_node, relationship, decision
    ) -> GraphEdge:  # noqa: ANN001
        self.calls += 1
        return GraphEdge(
            repository=repository,
            from_node=from_node,
            to_node=to_node,
            relationship=relationship,
        )

    def migrate_schema(self, repository, target_version, decision) -> MigrationResult:  # noqa: ANN001
        self.calls += 1
        return MigrationResult(
            repository=repository,
            from_version=SchemaVersion(major=1, minor=0),
            to_version=target_version,
            applied=True,
        )


class RecordingObservability:
    """Captures emitted events to assert metadata-only payloads."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def record_event(self, name, metadata=None) -> None:  # noqa: ANN001
        self.events.append((name, dict(metadata or {})))

    def increment_counter(self, name, value=1, metadata=None) -> None:  # noqa: ANN001
        return None

    def start_span(self, name, metadata=None):  # noqa: ANN001
        raise NotImplementedError


# --------------------------------------------------------------- valid path


def test_valid_upsert_delegates_exactly_once() -> None:
    store = RecordingStore()
    svc = ApprovalBoundMutationService(store)
    adr = adr_record()
    dec = decision(repo(), upsert_fingerprint(repo(), adr))
    node = svc.upsert_adr_node(repo(), adr, dec)
    assert isinstance(node, NodeId)
    assert store.calls == 1


def test_valid_add_relationship_delegates_once() -> None:
    store = RecordingStore()
    svc = ApprovalBoundMutationService(store)
    a = NodeId(repository=repo(), value="a")
    b = NodeId(repository=repo(), value="b")
    fp = relationship_fingerprint(repo(), a, b, RelationshipType.SUPERSEDES)
    edge = svc.add_relationship(
        repo(), a, b, RelationshipType.SUPERSEDES, decision(repo(), fp)
    )
    assert isinstance(edge, GraphEdge)
    assert store.calls == 1


def test_valid_migrate_schema_delegates_once() -> None:
    store = RecordingStore()
    svc = ApprovalBoundMutationService(store)
    target = SchemaVersion(major=2, minor=0)
    fp = migrate_fingerprint(repo(), target)
    result = svc.migrate_schema(repo(), target, decision(repo(), fp))
    assert isinstance(result, MigrationResult)
    assert store.calls == 1


# ------------------------------------------------- invalid paths: zero calls


def test_none_decision_rejected_before_adapter() -> None:
    store = RecordingStore()
    svc = ApprovalBoundMutationService(store)
    with pytest.raises(ApprovalRequiredError):
        svc.upsert_adr_node(repo(), adr_record(), None)
    assert store.calls == 0


def test_unapproved_decision_rejected_before_adapter() -> None:
    store = RecordingStore()
    svc = ApprovalBoundMutationService(store)
    adr = adr_record()
    dec = decision(repo(), upsert_fingerprint(repo(), adr), approved=False)
    with pytest.raises(ApprovalRequiredError):
        svc.upsert_adr_node(repo(), adr, dec)
    assert store.calls == 0


def test_repository_mismatch_rejected_before_adapter() -> None:
    store = RecordingStore()
    svc = ApprovalBoundMutationService(store)
    adr = adr_record(repo("alpha"))
    # Decision scoped to a different repository than the mutation.
    dec = decision(repo("beta"), upsert_fingerprint(repo("alpha"), adr))
    with pytest.raises(DecisionRepositoryMismatchError):
        svc.upsert_adr_node(repo("alpha"), adr, dec)
    assert store.calls == 0


def test_content_hash_mismatch_rejected_before_adapter() -> None:
    store = RecordingStore()
    svc = ApprovalBoundMutationService(store)
    adr = adr_record()
    dec = decision(
        repo(), upsert_fingerprint(repo(), adr), content_hash="d" * 64
    )
    with pytest.raises(DraftContentMismatchError):
        svc.upsert_adr_node(repo(), adr, dec)
    assert store.calls == 0


def test_target_fingerprint_mismatch_rejected_before_adapter() -> None:
    store = RecordingStore()
    svc = ApprovalBoundMutationService(store)
    adr = adr_record()
    dec = decision(repo(), "fingerprint-for-a-different-mutation")
    with pytest.raises(MutationFingerprintMismatchError):
        svc.upsert_adr_node(repo(), adr, dec)
    assert store.calls == 0


def test_one_shot_decision_cannot_be_replayed() -> None:
    store = RecordingStore()
    svc = ApprovalBoundMutationService(store)
    adr = adr_record()
    dec = decision(repo(), upsert_fingerprint(repo(), adr))
    svc.upsert_adr_node(repo(), adr, dec)
    with pytest.raises(DecisionAlreadyConsumedError):
        svc.upsert_adr_node(repo(), adr, dec)
    assert store.calls == 1


# -------------------------------------------------------- observability shape


def test_valid_mutation_emits_metadata_only_observability() -> None:
    store = RecordingStore()
    obs = RecordingObservability()
    svc = ApprovalBoundMutationService(store, observability=obs)
    adr = adr_record()
    dec = decision(repo(), upsert_fingerprint(repo(), adr))
    svc.upsert_adr_node(repo(), adr, dec)

    assert obs.events, "expected an observability event"
    _name, metadata = obs.events[-1]
    # Only small, non-sensitive metadata identifiers/keys are present.
    assert metadata["repository"] == repo().key
    assert metadata["adr_id"] == "adr-1"
    assert metadata["decision_id"] == "decision-1"
    # The raw ADR markdown / rationale body must never be exported.
    for value in metadata.values():
        assert "secret rationale body" not in str(value)
    assert "markdown" not in metadata
