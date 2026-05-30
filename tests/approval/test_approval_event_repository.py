"""Slice S010-01: durable, append-only review event capture.

Proves every reviewer outcome (approve, approve-after-edit, reject, defer) is
persisted as an immutable :class:`ApprovalEvent` row, that non-approving
outcomes mint no capability, and that the records survive a store reopen
(durability independent of any in-flight workflow checkpoint).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.approval._helpers import (
    DRAFT_HASH,
    FixedClock,
    SequentialIds,
    build_command,
    build_context,
    build_repo,
    sha256_lf,
)

from living_adr.approval.minting import record_review_outcome
from living_adr.approval.models import ApprovalEvent
from living_adr.approval.repository import (
    InMemoryApprovalAuditRepository,
    SqliteApprovalAuditRepository,
)
from living_adr.workflow.state import ReviewAction


def test_record_review_outcome_persists_immutable_event() -> None:
    audit = InMemoryApprovalAuditRepository()
    clock = FixedClock()
    ids = SequentialIds("evt")
    repo = build_repo()

    event = record_review_outcome(
        repo,
        build_command(ReviewAction.APPROVE),
        build_context(repo),
        audit=audit,
        clock=clock,
        id_provider=ids,
    )

    assert isinstance(event, ApprovalEvent)
    assert event.review_event_id == "evt-1"
    assert event.repository == repo
    assert event.reviewer_id == "lead-1"
    assert event.action is ReviewAction.APPROVE
    assert event.workflow_thread_id == "wf-thread-1"
    assert event.adr_draft_id == "draft-1"
    assert event.adr_draft_content_hash == DRAFT_HASH
    assert event.recorded_at == clock()
    # Slice 1 does not mint capabilities yet.
    assert event.decision_id is None
    assert event.authorizing is True

    stored = audit.get_review_event("evt-1")
    assert stored == event


@pytest.mark.parametrize(
    ("action", "authorizing"),
    [
        (ReviewAction.APPROVE, True),
        (ReviewAction.APPROVE_AFTER_EDIT, True),
        (ReviewAction.REJECT, False),
        (ReviewAction.DEFER, False),
    ],
)
def test_all_outcomes_recorded_with_authorizing_flag(
    action: ReviewAction, authorizing: bool
) -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    event = record_review_outcome(
        repo,
        build_command(action, reviewer_id="lead-2"),
        build_context(repo),
        audit=audit,
        clock=FixedClock(),
        id_provider=SequentialIds("evt"),
        reason="needs more evidence" if action is ReviewAction.REJECT else None,
    )
    assert event.action is action
    assert event.authorizing is authorizing
    # No capability is minted for any outcome in slice 1.
    assert event.decision_id is None
    if action is ReviewAction.REJECT:
        assert event.reason == "needs more evidence"


def test_approve_after_edit_binds_edited_content_hash() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    edited = (
        "# Title: Edited\n## Status\nProposed\n## Context\nc\n"
        "## Decision\nd\n## Consequences\ne\n"
    )
    edited_hash = sha256_lf(edited)
    event = record_review_outcome(
        repo,
        build_command(
            ReviewAction.APPROVE_AFTER_EDIT,
            edited_content=edited,
            edited_content_hash=edited_hash,
        ),
        build_context(repo),
        audit=audit,
        clock=FixedClock(),
        id_provider=SequentialIds("evt"),
    )
    # The reviewed content hash is the *edited* hash, not the original draft.
    assert event.adr_draft_content_hash == edited_hash
    assert event.adr_draft_content_hash != DRAFT_HASH


def test_review_events_are_append_only() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    event = record_review_outcome(
        repo,
        build_command(ReviewAction.APPROVE),
        build_context(repo),
        audit=audit,
        clock=FixedClock(),
        id_provider=SequentialIds("evt"),
    )
    # Re-recording the same id must be rejected (immutable append-only log).
    with pytest.raises(ValueError):
        audit.record_review_event(event)


def test_sqlite_review_events_survive_reopen(tmp_path: Path) -> None:
    db = tmp_path / "approval-audit.sqlite"
    repo = build_repo()

    store = SqliteApprovalAuditRepository(db)
    record_review_outcome(
        repo,
        build_command(ReviewAction.APPROVE, reviewer_id="lead-3"),
        build_context(repo),
        audit=store,
        clock=FixedClock(),
        id_provider=SequentialIds("evt"),
    )
    record_review_outcome(
        repo,
        build_command(ReviewAction.REJECT, reviewer_id="lead-3"),
        build_context(repo, draft_id="draft-2"),
        audit=store,
        clock=FixedClock(),
        id_provider=lambda: "evt-reject",
        reason="not significant",
    )
    store.close()

    # Reopen a fresh connection against the same file: rows are durable.
    reopened = SqliteApprovalAuditRepository(db)
    events = reopened.list_review_events(repository_key=repo.key)
    assert len(events) == 2
    actions = {e.action for e in events}
    assert actions == {ReviewAction.APPROVE, ReviewAction.REJECT}
    reject = next(e for e in events if e.action is ReviewAction.REJECT)
    assert reject.authorizing is False
    assert reject.reason == "not significant"
    reopened.close()
