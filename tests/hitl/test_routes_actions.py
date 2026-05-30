"""SL-003 tests: approve/reject POST actions with token + nonce protection.

Proves the review forms are guarded by the local UI token and a signed per-review
nonce, that valid submissions hand feature 015 the exact typed
``ReviewResumeCommand`` (and mint no approval capability), and that reject
requires a reason without ever logging it.
"""

from __future__ import annotations

from starlette.testclient import TestClient
from tests.hitl._fakes import gateway_with_one_pending, sample_payload

from living_adr.apps.workflow_service.hitl_routes import create_hitl_app
from living_adr.hitl.auth import NonceSigner
from living_adr.workflow.state import ReviewAction

TOKEN = "ui-secret-token"
NONCE_SECRET = "nonce-secret"
DRAFT_HASH = sample_payload().draft_content_hash


def _app(gateway):
    return create_hitl_app(
        gateway=gateway,
        ui_token=TOKEN,
        nonce_secret=NONCE_SECRET,
        reviewer_id="lead-1",
    )


def _client(gateway) -> TestClient:
    return TestClient(_app(gateway), follow_redirects=False)


def _nonce(thread_id: str = "wf-1") -> str:
    return NonceSigner(NONCE_SECRET).issue(thread_id, DRAFT_HASH)


def _auth() -> dict[str, str]:
    return {"X-UI-Token": TOKEN}


def test_approve_submits_resume_command_without_capability() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "approve",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
            "edited_content": "",
            "reason": "",
        },
    )
    assert response.status_code in (302, 303)
    assert len(gateway.submitted) == 1
    thread_id, command = gateway.submitted[0]
    assert thread_id == "wf-1"
    assert command.action is ReviewAction.APPROVE
    assert command.reviewer_id == "lead-1"
    assert command.edited_content is None
    assert command.edited_content_hash is None
    # Feature 009 mints no approval capability — that is feature 010.
    assert command.approved_decision is None


def test_reject_with_reason_submits_reject_command() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "reject",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
            "reason": "Insufficient evidence for this decision.",
        },
    )
    assert response.status_code in (302, 303)
    assert len(gateway.submitted) == 1
    _thread, command = gateway.submitted[0]
    assert command.action is ReviewAction.REJECT
    assert command.approved_decision is None


def test_reject_without_reason_is_validation_error() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "reject",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
            "reason": "   ",
        },
    )
    assert response.status_code == 400
    assert gateway.submitted == []
    # Re-renders the review page with an associated error.
    assert "reason-error" in response.text


def test_post_without_token_is_denied() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        data={
            "action": "approve",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
        },
    )
    assert response.status_code == 401
    assert gateway.submitted == []
    assert "draft-1" not in response.text  # no draft content leaked


def test_post_with_bad_nonce_is_rejected() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "approve",
            "nonce": "forged-nonce",
            "draft_content_hash": DRAFT_HASH,
        },
    )
    assert response.status_code == 400
    assert gateway.submitted == []


def test_get_review_page_issues_a_nonce_when_token_configured() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    body = client.get("/hitl/reviews/wf-1", headers=_auth()).text
    assert _nonce() in body


def test_get_review_page_without_token_is_denied() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.get("/hitl/reviews/wf-1")
    assert response.status_code == 401
    assert "draft-1" not in response.text
