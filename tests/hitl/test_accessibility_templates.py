"""SL-002+ tests: accessible semantic HTML for the review template.

Asserts landmarks, heading hierarchy, labelled controls, grouped action radios,
evidence presentation, and that confidence is conveyed with text (not color
alone). SL-006 hardens these into explicit quality gates.
"""

from __future__ import annotations

from starlette.testclient import TestClient
from tests.hitl._fakes import gateway_with_one_pending

from living_adr.apps.workflow_service.hitl_routes import create_hitl_app


def _review_html(thread_id: str = "wf-1") -> str:
    app = create_hitl_app(gateway=gateway_with_one_pending(thread_id))
    return TestClient(app).get(f"/hitl/reviews/{thread_id}").text


def test_single_main_landmark_and_heading_hierarchy() -> None:
    html = _review_html()
    assert html.count("<main") == 1
    assert "<h1" in html
    assert "<h2" in html


def test_action_radios_are_grouped_with_fieldset_legend() -> None:
    html = _review_html()
    assert "<fieldset" in html
    assert "<legend" in html
    # All four allowed actions are reachable as labelled controls.
    for action in ("approve", "approve_after_edit", "reject", "defer"):
        assert f'value="{action}"' in html


def test_edit_textarea_has_associated_label() -> None:
    html = _review_html()
    assert 'for="edited_content"' in html
    assert 'id="edited_content"' in html
    assert "<textarea" in html


def test_evidence_ids_rendered_as_list() -> None:
    html = _review_html()
    assert "<ul" in html or "<ol" in html
    assert "ev-1" in html
    assert "ev-2" in html


def test_confidence_shown_with_text_not_only_color() -> None:
    html = _review_html()
    # Textual confidence band, not just a colored bar.
    assert "confidence" in html.lower()
    assert ("High confidence" in html) or ("82" in html)
