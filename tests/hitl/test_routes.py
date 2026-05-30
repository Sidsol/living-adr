"""SL-002+ tests: FastAPI HITL review routes (GET render, not-found state).

Uses Starlette's TestClient against the app built by ``create_hitl_app`` with a
fake gateway. SL-002 covers the GET review page and the accessible not-found
state; later slices add POST actions, auth, and status pages.
"""

from __future__ import annotations

from starlette.testclient import TestClient
from tests.hitl._fakes import gateway_with_one_pending

from living_adr.apps.workflow_service.hitl_routes import create_hitl_app


def _client(gateway, **kwargs) -> TestClient:
    app = create_hitl_app(gateway=gateway, **kwargs)
    return TestClient(app)


def test_get_review_page_renders_pending_draft() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.get("/hitl/reviews/wf-1")
    assert response.status_code == 200
    body = response.text
    assert "github.com/acme/widgets" in body
    assert "draft-1" in body
    assert "ev-1" in body and "ev-2" in body
    # Provisional, non-authoritative copy must be present.
    assert "provisional" in body.lower()


def test_get_review_page_escapes_draft_markup() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    body = client.get("/hitl/reviews/wf-1").text
    # The draft preview contains "<audit>"; it must be HTML-escaped, never raw.
    assert "<audit>" not in body
    assert "&lt;audit&gt;" in body


def test_get_review_page_lists_pending_index() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.get("/hitl/reviews")
    assert response.status_code == 200
    assert "wf-1" in response.text


def test_get_missing_review_returns_accessible_not_found() -> None:
    gateway = gateway_with_one_pending("wf-1")
    client = _client(gateway)
    response = client.get("/hitl/reviews/does-not-exist")
    assert response.status_code == 404
    body = response.text
    # No internals/draft content leaked in the not-found state.
    assert "Traceback" not in body
    assert "draft-1" not in body
    assert "<main" in body  # still an accessible page
