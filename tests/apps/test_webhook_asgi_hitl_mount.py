"""Phase 4: the HITL review UI is mounted on the receiver app/port.

The receiver's /healthz and /webhooks/github routes are matched first; the
mounted HITL app serves the token-guarded /hitl/... review surface on the same
port.
"""

from __future__ import annotations

from starlette.testclient import TestClient
from tests.hitl._fakes import gateway_with_one_pending

from living_adr.apps.workflow_service.asgi import create_webhook_app
from living_adr.apps.workflow_service.hitl_routes import create_hitl_app
from living_adr.apps.workflow_service.webhooks import GitHubWebhookHandler

UI_TOKEN = "ui-token-xyz"  # noqa: S105 - test fixture


def _client() -> TestClient:
    hitl = create_hitl_app(
        gateway=gateway_with_one_pending("wf-1"), ui_token=UI_TOKEN
    )
    handler = GitHubWebhookHandler(secret="whsec")  # noqa: S106 - test fixture
    return TestClient(create_webhook_app(handler=handler, hitl_app=hitl))


def test_healthz_still_served_with_hitl_mounted() -> None:
    response = _client().get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hitl_review_page_served_with_token() -> None:
    response = _client().get(
        "/hitl/reviews/wf-1", headers={"X-UI-Token": UI_TOKEN}
    )
    assert response.status_code == 200
    assert "draft-1" in response.text


def test_hitl_review_page_requires_token() -> None:
    response = _client().get("/hitl/reviews/wf-1")
    assert response.status_code == 401
