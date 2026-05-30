"""SL-004 tests: edit + approve-after-edit POST flow.

Valid edited Markdown is hashed and submitted as a feature 015
``ReviewResumeCommand(action="approve_after_edit")`` carrying the edited content
and its hash; invalid edits re-render the page with inline, associated errors and
preserve the reviewer's input. No approval capability is minted.
"""

from __future__ import annotations

from starlette.testclient import TestClient
from tests.hitl._fakes import gateway_with_one_pending, sample_payload

from living_adr.apps.workflow_service.hitl_routes import create_hitl_app
from living_adr.hitl.auth import NonceSigner
from living_adr.hitl.hashing import compute_edited_draft_hash
from living_adr.workflow.state import ReviewAction

TOKEN = "ui-secret-token"
NONCE_SECRET = "nonce-secret"
DRAFT_HASH = sample_payload().draft_content_hash

VALID_EDIT = (
    "# Title: Adopt event sourcing\n\n"
    "## Status\nProposed\n\n## Context\nWe need an audit trail.\n\n"
    "## Decision\nUse an append-only log.\n\n"
    "## Consequences\nMore storage.\n"
)


def _client(gateway) -> TestClient:
    app = create_hitl_app(
        gateway=gateway,
        ui_token=TOKEN,
        nonce_secret=NONCE_SECRET,
        reviewer_id="lead-1",
    )
    return TestClient(app, follow_redirects=False)


def _nonce(thread_id: str = "wf-1") -> str:
    return NonceSigner(NONCE_SECRET).issue(thread_id, DRAFT_HASH)


def _auth() -> dict[str, str]:
    return {"X-UI-Token": TOKEN}


def test_approve_after_edit_submits_edited_content_and_hash() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "approve_after_edit",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
            "edited_content": VALID_EDIT,
        },
    )
    assert response.status_code in (302, 303)
    assert len(gateway.submitted) == 1
    _thread, command = gateway.submitted[0]
    assert command.action is ReviewAction.APPROVE_AFTER_EDIT
    assert command.edited_content == VALID_EDIT
    assert command.edited_content_hash == compute_edited_draft_hash(VALID_EDIT)
    # Still no approval capability minted by the UI.
    assert command.approved_decision is None


def test_approve_after_edit_invalid_content_reprrenders_with_errors() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    bad = "# Title only, no required sections"
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "approve_after_edit",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
            "edited_content": bad,
        },
    )
    assert response.status_code == 400
    assert gateway.submitted == []
    body = response.text
    # Inline, associated error and preserved input.
    assert "edited_content-error" in body
    assert "aria-invalid=\"true\"" in body
    assert bad in body


def test_approve_after_edit_empty_content_is_rejected() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "approve_after_edit",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
            "edited_content": "   ",
        },
    )
    assert response.status_code == 400
    assert gateway.submitted == []
