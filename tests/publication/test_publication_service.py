"""Slice S011-04 RED tests: SCM-backed publication committer + conflict retry.

The committer lists the configured ADR directory through the provider-neutral
contents port, allocates the next number (FR-7), renders the path from the
configured template (FR-5), embeds the ``livingadr_decision_id`` marker (FR-10),
and commits the approved Markdown. A moved branch head (CommitConflictError) is
retried within a bounded budget; exhaustion dead-letters and raises. An existing
same-decision file is detected and never committed twice (idempotent recovery).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.publication._helpers import (
    FakeSCMContents,
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
from living_adr.core.config import PublicationPolicy
from living_adr.core.graph.approval_bound_mutation import upsert_fingerprint
from living_adr.publication.models import (
    ADRPublicationRequest,
    PublicationConflictExhaustedError,
    PublicationStatus,
)
from living_adr.publication.numbering import decision_marker
from living_adr.publication.repository import InMemoryPublicationRepository
from living_adr.publication.service import (
    ADRPublicationService,
    AuthorizedPublication,
    SCMContentsPublicationCommitter,
    resolve_publication_target,
)


def _target(repo, policy=PublicationPolicy.PUBLISH_TO_GITHUB):  # noqa: ANN001
    return resolve_publication_target(build_config(repo, policy=policy))


def _request(repo, adr, decision, policy=PublicationPolicy.PUBLISH_TO_GITHUB):  # noqa: ANN001
    return ADRPublicationRequest(
        repository=repo,
        adr=adr,
        decision=decision,
        policy=policy,
        target=_target(repo, policy),
    )


def _authorization(repo, adr, decision):  # noqa: ANN001
    return AuthorizedPublication(
        decision=decision,
        consumption=ConsumptionRecord(
            decision_id=decision.decision_id,
            target_fingerprint=upsert_fingerprint(repo, adr),
            repository_key=repo.key,
            outcome="mutated",
            node_id=f"node:{adr.adr_id}",
            consumed_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        ),
    )


# --- numbering + path + marker --------------------------------------------


def test_committer_allocates_first_adr_into_empty_directory() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    contents = FakeSCMContents()
    committer = SCMContentsPublicationCommitter(contents)

    outcome = committer.commit(
        _request(repo, adr, decision),
        _target(repo),
        _authorization(repo, adr, decision),
    )

    assert outcome.created is True
    assert outcome.target_path == "docs/adr/0001-adopt-durable-approval-audit.md"
    # The committed body carries the decision marker for recovery (FR-10).
    body = contents.read_file(repo, "main", outcome.target_path).text
    assert decision_marker(decision.decision_id) in body


def test_committer_allocates_next_number_after_existing_adrs() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    contents = FakeSCMContents(
        {
            "docs/adr/0001-old.md": "# one\n",
            "docs/adr/0002-older.md": "# two\n",
            "docs/adr/readme.md": "not an adr\n",
        }
    )
    committer = SCMContentsPublicationCommitter(contents)

    outcome = committer.commit(
        _request(repo, adr, decision),
        _target(repo),
        _authorization(repo, adr, decision),
    )

    assert outcome.target_path == "docs/adr/0003-adopt-durable-approval-audit.md"


def test_committer_detects_existing_same_decision_file_and_skips_commit() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    existing = f"{decision_marker(decision.decision_id)}\n# already here\n"
    contents = FakeSCMContents({"docs/adr/0007-prior.md": existing})
    committer = SCMContentsPublicationCommitter(contents)

    outcome = committer.commit(
        _request(repo, adr, decision),
        _target(repo),
        _authorization(repo, adr, decision),
    )

    assert outcome.created is False
    assert outcome.target_path == "docs/adr/0007-prior.md"
    assert contents.create_calls == []  # no second file committed


# --- bounded conflict retry -----------------------------------------------


def test_committer_retries_then_commits_after_transient_conflicts() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    contents = FakeSCMContents(conflicts=2)
    committer = SCMContentsPublicationCommitter(contents, max_attempts=3)

    outcome = committer.commit(
        _request(repo, adr, decision),
        _target(repo),
        _authorization(repo, adr, decision),
    )

    assert outcome.created is True
    assert len(contents.create_calls) == 3  # two conflicts + one success


def test_committer_exhausts_retries_and_raises_conflict_exhausted() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    contents = FakeSCMContents(conflicts=99)
    committer = SCMContentsPublicationCommitter(contents, max_attempts=3)

    with pytest.raises(PublicationConflictExhaustedError):
        committer.commit(
            _request(repo, adr, decision),
            _target(repo),
            _authorization(repo, adr, decision),
        )
    assert len(contents.create_calls) == 3


# --- service integration with the real committer --------------------------


def _seed_consumed_decision(audit, repo, adr, decision) -> None:  # noqa: ANN001
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


def test_service_publishes_through_scm_committer_end_to_end() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    audit = InMemoryApprovalAuditRepository()
    _seed_consumed_decision(audit, repo, adr, decision)
    contents = FakeSCMContents()
    service = ADRPublicationService(
        audit=audit,
        records=InMemoryPublicationRepository(),
        committer=SCMContentsPublicationCommitter(contents),
        clock=FixedClock(),
        id_provider=SequentialIds("pub-audit"),
    )

    result = service.publish(_request(repo, adr, decision))

    assert result.status is PublicationStatus.COMMITTED
    assert result.target_path == "docs/adr/0001-adopt-durable-approval-audit.md"
    # The file really landed in the fake repo with the decision marker.
    body = contents.read_file(repo, "main", result.target_path).text
    assert decision_marker(decision.decision_id) in body
    linked = [
        e
        for e in audit.list_audit_events(decision_id=decision.decision_id)
        if e.event_type is AuditEventType.PUBLICATION_LINKED
    ]
    assert len(linked) == 1


def test_service_dead_letters_when_conflicts_exhaust() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    audit = InMemoryApprovalAuditRepository()
    _seed_consumed_decision(audit, repo, adr, decision)
    records = InMemoryPublicationRepository()
    contents = FakeSCMContents(conflicts=99)
    service = ADRPublicationService(
        audit=audit,
        records=records,
        committer=SCMContentsPublicationCommitter(contents, max_attempts=3),
        clock=FixedClock(),
        id_provider=SequentialIds("pub-audit"),
    )

    with pytest.raises(PublicationConflictExhaustedError):
        service.publish(_request(repo, adr, decision))

    persisted = records.get(decision.decision_id)
    assert persisted is not None
    assert persisted.status is PublicationStatus.DEAD_LETTERED
