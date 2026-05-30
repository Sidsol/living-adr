"""TASK-015: full walking-skeleton smoke E2E.

Demonstrates the complete visible path end to end with stubs only:
replay -> classify -> draft -> accept -> approval-bound persist -> MCP answer.
Asserts stub labeling, approved-only citations, duplicate-replay idempotency,
and the source-of-truth discipline (drafts/evidence are not authoritative).
"""

from __future__ import annotations

from living_adr.apps.mcp_context_server.main import SmokeMcpContextServer
from living_adr.graph.stub_store import ApprovalBoundStubStore
from living_adr.hitl.stub_review import accept_draft
from living_adr.workflow.smoke_fixture import SmokeEventReplayer, smoke_repository
from living_adr.workflow.smoke_flow import classify_structural_change, draft_adr


def test_full_walking_skeleton_smoke() -> None:
    repo = smoke_repository()
    replayer = SmokeEventReplayer()
    store = ApprovalBoundStubStore()

    # 1) Replay one merged-PR-like event.
    replay = replayer.replay()
    assert replay.is_duplicate is False
    event = replay.event
    assert event.repository == repo

    # 2) Deterministic stub classify + draft (explicitly labeled non-production).
    change, evidence = classify_structural_change(event)
    draft = draft_adr(change, evidence)
    assert draft.is_stub is True
    assert "smoke" in draft.rendered_markdown.lower()
    assert "claude" not in draft.rendered_markdown.lower()

    # 3) Stub HITL accept mints an approved decision bound to this draft.
    decision = accept_draft(draft, change, reviewer_id="lead-1")
    assert decision.approved is True
    assert decision.adr_draft_id == draft.draft_id

    # 4) Approval-bound persistence creates exactly one approved ADRRecord.
    record = store.persist_approved_adr(
        event=event, evidence=evidence, change=change, draft=draft, decision=decision
    )
    assert record.status == "approved"
    assert len(store.list_approved(repo)) == 1
    # Provenance links the full chain.
    assert record.provenance.source_delivery_id == event.delivery_id
    assert record.provenance.decision_id == decision.decision_id

    # 5) MCP-style answer_why returns approved, cited context only.
    server = SmokeMcpContextServer(query=store)
    answer = server.answer_why_smoke(
        repository=repo,
        question="Why was the httpx dependency adopted?",
        code_area_id="src/app/client.py",
    )
    assert answer.found is True
    assert answer.adr_id == record.adr_id
    assert f"adr:{record.adr_id}" in answer.citations
    # The draft id is NOT cited as authoritative rationale.
    assert all(draft.draft_id not in c for c in answer.citations)

    # 6) Duplicate replay is idempotent: no second approved record is created.
    second = replayer.replay()
    assert second.is_duplicate is True
    assert len(store.list_approved(repo)) == 1


def test_no_approved_context_before_persistence() -> None:
    repo = smoke_repository()
    store = ApprovalBoundStubStore()
    server = SmokeMcpContextServer(query=store)
    answer = server.answer_why_smoke(repository=repo, question="Why?")
    assert answer.found is False
    assert answer.adr_id is None
