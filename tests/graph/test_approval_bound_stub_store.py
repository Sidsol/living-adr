"""SL-004 RED tests: approval-bound stub persistence guard.

The smoke store must refuse to create an authoritative ``ADRRecord`` without a
valid ``ApprovedReviewDecision`` (SM-05; FM-13 excessive agency), must store
exactly one approved record when the decision matches the reviewed draft, must
reject content drift between the reviewed draft and the stored draft
(DraftContentMismatch), and must retain full provenance.
"""

from __future__ import annotations

import pytest

from living_adr.core.models import ADRRecord
from living_adr.graph.stub_store import (
    ApprovalBoundStubStore,
    DraftContentMismatchError,
    UnauthorizedMutationError,
)
from living_adr.hitl.stub_review import accept_draft
from living_adr.workflow.smoke_fixture import (
    merged_pr_fixture,
    normalize_to_scm_event,
)
from living_adr.workflow.smoke_flow import classify_structural_change, draft_adr


def _pipeline():
    event = normalize_to_scm_event(merged_pr_fixture())
    change, evidence = classify_structural_change(event)
    draft = draft_adr(change, evidence)
    decision = accept_draft(draft, change, reviewer_id="lead-1")
    return event, evidence, change, draft, decision


def test_persist_without_decision_is_rejected() -> None:
    event, evidence, change, draft, _ = _pipeline()
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


def test_persist_with_matching_decision_stores_one_record() -> None:
    event, evidence, change, draft, decision = _pipeline()
    store = ApprovalBoundStubStore()
    record = store.persist_approved_adr(
        event=event,
        evidence=evidence,
        change=change,
        draft=draft,
        decision=decision,
    )
    assert isinstance(record, ADRRecord)
    assert record.status == "approved"
    assert record.repository == event.repository
    approved = store.list_approved(event.repository)
    assert len(approved) == 1
    assert approved[0].adr_id == record.adr_id


def test_persisted_record_links_full_provenance() -> None:
    event, evidence, change, draft, decision = _pipeline()
    store = ApprovalBoundStubStore()
    record = store.persist_approved_adr(
        event=event,
        evidence=evidence,
        change=change,
        draft=draft,
        decision=decision,
    )
    prov = record.provenance
    assert prov.source_delivery_id == event.delivery_id
    assert prov.evidence_id == evidence.evidence_id
    assert prov.structural_change_id == change.change_id
    assert prov.adr_draft_id == draft.draft_id
    assert prov.decision_id == decision.decision_id


def test_content_drift_after_approval_is_rejected() -> None:
    event, evidence, change, draft, decision = _pipeline()
    store = ApprovalBoundStubStore()
    tampered = draft.model_copy(
        update={"rendered_markdown": draft.rendered_markdown + "\n<edited>"}
    )
    with pytest.raises(DraftContentMismatchError):
        store.persist_approved_adr(
            event=event,
            evidence=evidence,
            change=change,
            draft=tampered,
            decision=decision,
        )
    assert store.list_approved(event.repository) == []


def test_idempotent_resubmission_does_not_duplicate() -> None:
    event, evidence, change, draft, decision = _pipeline()
    store = ApprovalBoundStubStore()
    first = store.persist_approved_adr(
        event=event, evidence=evidence, change=change, draft=draft, decision=decision
    )
    second = store.persist_approved_adr(
        event=event, evidence=evidence, change=change, draft=draft, decision=decision
    )
    assert first.adr_id == second.adr_id
    assert len(store.list_approved(event.repository)) == 1
