"""SL-005 tests: defer action, status pages, and missing/unauthorized states.

Defer resumes feature 015 without requiring a reason and mints no capability.
The status page is an accessible confirmation; missing threads and missing tokens
produce accessible 404/401 states that never leak draft content or internals.
"""

from __future__ import annotations

from starlette.testclient import TestClient
from tests.hitl._fakes import (
    FakeGateway,
    gateway_with_one_pending,
    sample_payload,
)

from living_adr.apps.workflow_service.hitl_routes import create_hitl_app
from living_adr.hitl.auth import NonceSigner
from living_adr.workflow.state import ReviewAction

TOKEN = "ui-secret-token"
NONCE_SECRET = "nonce-secret"
DRAFT_HASH = sample_payload().draft_content_hash


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


def test_defer_submits_defer_command_without_reason() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "defer",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
            "reason": "",
        },
    )
    assert response.status_code in (302, 303)
    assert len(gateway.submitted) == 1
    _thread, command = gateway.submitted[0]
    assert command.action is ReviewAction.DEFER
    assert command.approved_decision is None


def test_status_page_renders_accessible_confirmation() -> None:
    client = _client(gateway_with_one_pending("wf-1"))
    response = client.get(
        "/hitl/reviews/wf-1/status?action=approve&status=completed",
        headers=_auth(),
    )
    assert response.status_code == 200
    body = response.text
    assert "<main" in body
    assert 'role="status"' in body
    assert "approve" in body
    assert "completed" in body
    # The confirmation copy reiterates the non-authoritative boundary.
    assert "no approval capability" in body.lower()


def test_status_page_requires_token() -> None:
    client = _client(gateway_with_one_pending("wf-1"))
    response = client.get("/hitl/reviews/wf-1/status?action=approve")
    assert response.status_code == 401


def test_post_to_missing_thread_is_not_found() -> None:
    gateway = FakeGateway()  # no pending reviews
    client = _client(gateway)
    response = client.post(
        "/hitl/reviews/ghost/submit",
        headers=_auth(),
        data={
            "action": "approve",
            "nonce": NonceSigner(NONCE_SECRET).issue("ghost", DRAFT_HASH),
            "draft_content_hash": DRAFT_HASH,
        },
    )
    assert response.status_code == 404
    assert gateway.submitted == []
    assert "Traceback" not in response.text


def test_redirect_target_renders_when_followed() -> None:
    gateway = gateway_with_one_pending("wf-1")
    app = create_hitl_app(
        gateway=gateway,
        ui_token=TOKEN,
        nonce_secret=NONCE_SECRET,
        reviewer_id="lead-1",
    )
    client = TestClient(app, follow_redirects=True)
    response = client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "approve",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
        },
    )
    assert response.status_code == 200
    assert "Decision recorded" in response.text
