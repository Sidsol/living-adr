"""SL-005 RED tests: read-only MCP-style answer_why over approved context only.

The MCP-style wrapper must answer from stored approved ``ADRRecord`` context with
an answer, the ADR id, and citations; it must return a no-approved-context
response (never reading pending drafts or raw evidence) when nothing is approved,
and it must be read-only by construction (FM-15 MCP read-only trust boundary).
"""

from __future__ import annotations

from living_adr.apps.mcp_context_server.main import SmokeMcpContextServer
from living_adr.core.models import WhyAnswer
from living_adr.graph.stub_store import ApprovalBoundStubStore
from living_adr.hitl.stub_review import accept_draft
from living_adr.workflow.smoke_fixture import (
    SmokeEventReplayer,
    smoke_repository,
)
from living_adr.workflow.smoke_flow import classify_structural_change, draft_adr


def _store_with_approved_record() -> ApprovalBoundStubStore:
    event = SmokeEventReplayer().replay().event
    change, evidence = classify_structural_change(event)
    draft = draft_adr(change, evidence)
    decision = accept_draft(draft, change, reviewer_id="lead-1")
    store = ApprovalBoundStubStore()
    store.persist_approved_adr(
        event=event, evidence=evidence, change=change, draft=draft, decision=decision
    )
    return store


def test_answer_why_returns_cited_approved_context() -> None:
    store = _store_with_approved_record()
    server = SmokeMcpContextServer(query=store)
    answer = server.answer_why_smoke(
        repository=smoke_repository(),
        question="Why was the httpx dependency adopted?",
        code_area_id="src/app/client.py",
    )
    assert isinstance(answer, WhyAnswer)
    assert answer.found is True
    assert answer.adr_id is not None
    assert answer.answer
    assert any(c.startswith("adr:") for c in answer.citations)


def test_answer_why_without_approved_context_returns_empty_response() -> None:
    store = ApprovalBoundStubStore()  # nothing approved
    server = SmokeMcpContextServer(query=store)
    answer = server.answer_why_smoke(
        repository=smoke_repository(),
        question="Why was anything decided?",
    )
    assert answer.found is False
    assert answer.adr_id is None
    assert answer.citations == ()


def test_answer_why_is_read_only() -> None:
    store = _store_with_approved_record()
    before = {r.adr_id for r in store.list_approved(smoke_repository())}
    server = SmokeMcpContextServer(query=store)
    server.answer_why_smoke(repository=smoke_repository(), question="Why?")
    after = {r.adr_id for r in store.list_approved(smoke_repository())}
    assert before == after  # query did not mutate stored state
    # Server exposes no mutation surface.
    assert not hasattr(server, "persist_approved_adr")
