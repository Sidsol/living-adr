"""SL-004 E2E test: replay -> classify -> draft -> accept -> approved persistence.

Proves the cumulative smoke path through the approval-bound store and that an
unauthorized (decision-less) persistence attempt is rejected on the same path.
"""

from __future__ import annotations

import pytest

from living_adr.graph.stub_store import (
    ApprovalBoundStubStore,
    UnauthorizedMutationError,
)
from living_adr.hitl.stub_review import accept_draft
from living_adr.workflow.smoke_fixture import SmokeEventReplayer
from living_adr.workflow.smoke_flow import classify_structural_change, draft_adr


def test_event_to_approved_record_e2e() -> None:
    replay = SmokeEventReplayer().replay()
    event = replay.event
    change, evidence = classify_structural_change(event)
    draft = draft_adr(change, evidence)
    decision = accept_draft(draft, change, reviewer_id="lead-1")

    store = ApprovalBoundStubStore()
    record = store.persist_approved_adr(
        event=event,
        evidence=evidence,
        change=change,
        draft=draft,
        decision=decision,
    )

    assert record.status == "approved"
    assert len(store.list_approved(event.repository)) == 1
    assert store.fetch_adr(event.repository, record.adr_id) == record


def test_event_to_persistence_without_approval_is_blocked() -> None:
    replay = SmokeEventReplayer().replay()
    event = replay.event
    change, evidence = classify_structural_change(event)
    draft = draft_adr(change, evidence)

    store = ApprovalBoundStubStore()
    with pytest.raises(UnauthorizedMutationError):
        store.persist_approved_adr(
            event=event,
            evidence=evidence,
            change=change,
            draft=draft,
            decision=None,
        )
    assert store.list_approved(event.repository) == []
