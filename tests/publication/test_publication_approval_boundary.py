"""Slice S011-02 RED tests: approval-bound publish + idempotent prior results.

Proves publish-back is authorised only through feature 010's just-in-time
validation over a *consumed* approved decision, performs no SCM commit when
authorisation fails or policy skips GitHub, links every attempt to its
``decision_id`` via a ``PUBLICATION_LINKED`` audit row, and returns the prior
result for same-decision retries without committing a second file.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.publication._helpers import (
    FixedClock,
    SequentialIds,
    build_adr,
    build_config,
    build_decision,
    build_repo,
)

from living_adr.approval.models import (
    AuditEventType,
    ConsumptionRecord,
    MintedDecisionRecord,
)
from living_adr.approval.repository import InMemoryApprovalAuditRepository
from living_adr.core.approval import ApprovalError
from living_adr.core.config import PublicationPolicy
from living_adr.core.graph.approval_bound_mutation import upsert_fingerprint
from living_adr.publication.models import (
    ADRPublicationRequest,
    PublicationNotAuthorizedError,
    PublicationStatus,
    PublicationTargetMismatchError,
)
from living_adr.publication.repository import InMemoryPublicationRepository
from living_adr.publication.service import (
    ADRPublicationService,
    CommitOutcome,
    resolve_publication_target,
)


class SpyCommitter:
    """Records commit calls and returns a canned committed-file outcome."""

    def __init__(self) -> None:
        self.calls = 0

    def commit(self, request, target, authorization) -> CommitOutcome:  # noqa: ANN001
        self.calls += 1
        return CommitOutcome(
            target_path="docs/adr/0001-adopt-durable-approval-audit.md",
            commit_sha="commit-sha-1",
            created=True,
        )


def _seed_consumed_decision(audit, repo, adr, decision) -> None:
    """Simulate feature 010 having minted + consumed this decision."""

    fp = upsert_fingerprint(repo, adr)
    audit.record_minted_decision(
        MintedDecisionRecord(
            decision_id=decision.decision_id,
            review_event_id="rev-1",
            repository_key=repo.key,
            reviewer_id=decision.reviewer_id,
            adr_draft_id=adr.adr_id,
            adr_record_id=adr.adr_id,
            adr_draft_content_hash=adr.content_hash,
            target_fingerprint=fp,
            minted_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
            ttl_seconds=600,
        )
    )
    audit.record_consumption(
        ConsumptionRecord(
            decision_id=decision.decision_id,
            target_fingerprint=fp,
            repository_key=repo.key,
            outcome="mutated",
            node_id=f"node:{adr.adr_id}",
            consumed_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
    )


def _build(audit=None, committer=None):
    audit = audit or InMemoryApprovalAuditRepository()
    committer = committer or SpyCommitter()
    service = ADRPublicationService(
        audit=audit,
        records=InMemoryPublicationRepository(),
        committer=committer,
        clock=FixedClock(),
        id_provider=SequentialIds("pub-audit"),
    )
    return service, audit, committer


def _request(repo, adr, decision, policy=PublicationPolicy.PUBLISH_TO_GITHUB):
    return ADRPublicationRequest(
        repository=repo,
        adr=adr,
        decision=decision,
        policy=policy,
        target=resolve_publication_target(build_config(repo, policy=policy)),
    )


# --- authorisation gate (no SCM call without feature 010) -----------------


def test_missing_decision_is_unauthorised_and_does_not_commit() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    service, _audit, committer = _build()
    with pytest.raises(PublicationNotAuthorizedError):
        service.publish(_request(repo, adr, decision=None))
    assert committer.calls == 0


def test_decision_without_consumption_is_unauthorised() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    service, _audit, committer = _build()
    # No _seed_consumed_decision: feature 010 never consumed this decision.
    with pytest.raises(PublicationNotAuthorizedError):
        service.publish(_request(repo, adr, decision))
    assert committer.calls == 0


def test_fingerprint_drift_fails_validation_before_commit() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    audit = InMemoryApprovalAuditRepository()
    _seed_consumed_decision(audit, repo, adr, decision)
    service, _audit, committer = _build(audit=audit)
    # Publish a *different* ADR content under the same decision: the decision's
    # target fingerprint no longer authorises this mutation target.
    drifted = build_adr(repo, content_hash="drifted-hash")
    with pytest.raises(ApprovalError):
        service.publish(_request(repo, drifted, decision))
    assert committer.calls == 0
    failures = [
        e
        for e in audit.list_audit_events()
        if e.event_type is AuditEventType.VALIDATION_FAILED
    ]
    assert failures


# --- success + audit linkage ----------------------------------------------


def test_authorised_publish_commits_and_links_decision() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    audit = InMemoryApprovalAuditRepository()
    _seed_consumed_decision(audit, repo, adr, decision)
    service, _audit, committer = _build(audit=audit)

    result = service.publish(_request(repo, adr, decision))

    assert result.status is PublicationStatus.COMMITTED
    assert result.commit_sha == "commit-sha-1"
    assert result.decision_id == decision.decision_id
    assert committer.calls == 1
    linked = [
        e
        for e in audit.list_audit_events(decision_id=decision.decision_id)
        if e.event_type is AuditEventType.PUBLICATION_LINKED
    ]
    assert len(linked) == 1


# --- idempotency ----------------------------------------------------------


def test_same_decision_retry_returns_prior_without_second_commit() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    audit = InMemoryApprovalAuditRepository()
    _seed_consumed_decision(audit, repo, adr, decision)
    service, _audit, committer = _build(audit=audit)

    first = service.publish(_request(repo, adr, decision))
    second = service.publish(_request(repo, adr, decision))

    assert first.status is PublicationStatus.COMMITTED
    assert second.status is PublicationStatus.ALREADY_PUBLISHED
    assert second.idempotent is True
    assert second.commit_sha == first.commit_sha
    assert committer.calls == 1


def test_same_decision_different_target_is_rejected() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    audit = InMemoryApprovalAuditRepository()
    _seed_consumed_decision(audit, repo, adr, decision)
    service, _audit, committer = _build(audit=audit)

    service.publish(_request(repo, adr, decision))
    # A retry presenting the same decision_id but a different fingerprint
    # (e.g. a different policy → different target) must be rejected.
    with pytest.raises(PublicationTargetMismatchError):
        service.publish(
            _request(
                repo,
                adr,
                decision,
                policy=PublicationPolicy.PUBLISH_TO_GITHUB_AND_LIVINGADR,
            )
        )
    assert committer.calls == 1


# --- policy skip ----------------------------------------------------------


def test_livingadr_only_policy_skips_github_with_audit_linkage() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    audit = InMemoryApprovalAuditRepository()
    _seed_consumed_decision(audit, repo, adr, decision)
    service, _audit, committer = _build(audit=audit)

    result = service.publish(
        _request(repo, adr, decision, policy=PublicationPolicy.LIVINGADR_ONLY)
    )

    assert result.status is PublicationStatus.SKIPPED_BY_POLICY
    assert committer.calls == 0
    linked = [
        e
        for e in audit.list_audit_events(decision_id=decision.decision_id)
        if e.event_type is AuditEventType.PUBLICATION_LINKED
    ]
    assert len(linked) == 1
