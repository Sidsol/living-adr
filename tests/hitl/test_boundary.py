"""SL-006 boundary tests: capability/mutation discipline + metadata-only telemetry.

Proves feature 009 stays inside its lane:
* It mints no ``ApprovedReviewDecision`` and submits ``approved_decision=None``
  for every action (feature 010 owns capability minting + durable audit).
* Its source imports no graph store, approval-bound mutation service, Claude/
  Anthropic client, or GitHub publication provider.
* Its observability is metadata-only: raw draft bodies, reviewer edits, and
  rejection reasons never appear in any emitted event.
"""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient
from tests.hitl._fakes import gateway_with_one_pending, sample_payload

import living_adr.hitl.gateway as gateway_mod
import living_adr.hitl.models as models_mod
from living_adr.apps.workflow_service import hitl_routes
from living_adr.apps.workflow_service.hitl_routes import create_hitl_app
from living_adr.hitl import auth as auth_mod
from living_adr.hitl import hashing as hashing_mod
from living_adr.hitl import observability as obs_mod
from living_adr.hitl.auth import NonceSigner
from living_adr.hitl.observability import review_event_metadata
from living_adr.workflow.state import ReviewResumeCommand

TOKEN = "ui-secret-token"
NONCE_SECRET = "nonce-secret"
DRAFT_HASH = sample_payload().draft_content_hash

FORBIDDEN_SYMBOLS = (
    "ArchitectureGraphStore",
    "ApprovalBoundMutationService",
    "GraphMutationService",
    "ApprovedReviewDecision",
    "accept_draft",
    "anthropic",
    "Anthropic",
    "GitHubProvider",
    "publish_to_github",
)

FEATURE_009_SOURCE_FILES = (
    models_mod.__file__,
    gateway_mod.__file__,
    auth_mod.__file__,
    hashing_mod.__file__,
    obs_mod.__file__,
    hitl_routes.__file__,
)


class RecordingObservability:
    """Captures every emitted event so we can scan for leaked sensitive content."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def record_event(self, name: str, metadata=None) -> None:
        self.events.append((name, dict(metadata or {})))

    def increment_counter(self, name, value=1, metadata=None) -> None:
        self.events.append((name, dict(metadata or {})))

    def start_span(self, name, metadata=None):  # pragma: no cover - unused
        from contextlib import nullcontext

        return nullcontext()


def _auth() -> dict[str, str]:
    return {"X-UI-Token": TOKEN}


def _nonce(thread_id: str = "wf-1") -> str:
    return NonceSigner(NONCE_SECRET).issue(thread_id, DRAFT_HASH)


def test_no_forbidden_symbol_in_feature_009_source() -> None:
    for source_file in FEATURE_009_SOURCE_FILES:
        text = Path(source_file).read_text(encoding="utf-8")
        for symbol in FORBIDDEN_SYMBOLS:
            assert symbol not in text, f"{symbol} leaked into {source_file}"


def test_every_action_mints_no_approval_capability() -> None:
    for action in ("approve", "approve_after_edit", "reject", "defer"):
        gateway = gateway_with_one_pending("wf-1")
        client = TestClient(
            create_hitl_app(
                gateway=gateway,
                ui_token=TOKEN,
                nonce_secret=NONCE_SECRET,
                reviewer_id="lead-1",
            ),
            follow_redirects=False,
        )
        data = {
            "action": action,
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
            "reason": "needs more evidence" if action == "reject" else "",
            "edited_content": (
                "# Title: x\n## Status\nProposed\n## Context\nc\n"
                "## Decision\nd\n## Consequences\ne\n"
                if action == "approve_after_edit"
                else ""
            ),
        }
        client.post("/hitl/reviews/wf-1/submit", headers=_auth(), data=data)
        assert len(gateway.submitted) == 1
        _thread, command = gateway.submitted[0]
        assert isinstance(command, ReviewResumeCommand)
        assert command.approved_decision is None


def test_telemetry_never_contains_raw_draft_edit_or_reason() -> None:
    obs = RecordingObservability()
    secret_edit = (
        "# Title: SENSITIVE_EDIT_MARKER\n## Status\nProposed\n"
        "## Context\nTOPSECRET_CONTEXT\n## Decision\nd\n## Consequences\ne\n"
    )
    secret_reason = "REASON_MARKER_should_not_be_logged"
    gateway = gateway_with_one_pending("wf-1")
    client = TestClient(
        create_hitl_app(
            gateway=gateway,
            ui_token=TOKEN,
            nonce_secret=NONCE_SECRET,
            reviewer_id="lead-1",
            observability=obs,
        ),
        follow_redirects=False,
    )
    # View, then approve-after-edit with sensitive content.
    client.get("/hitl/reviews/wf-1", headers=_auth())
    client.post(
        "/hitl/reviews/wf-1/submit",
        headers=_auth(),
        data={
            "action": "approve_after_edit",
            "nonce": _nonce(),
            "draft_content_hash": DRAFT_HASH,
            "edited_content": secret_edit,
            "reason": secret_reason,
        },
    )
    assert obs.events, "expected telemetry to be emitted"
    blob = repr(obs.events)
    for marker in (
        "SENSITIVE_EDIT_MARKER",
        "TOPSECRET_CONTEXT",
        "REASON_MARKER_should_not_be_logged",
        sample_payload().draft_preview,
    ):
        assert marker not in blob


def test_review_event_metadata_drops_disallowed_keys() -> None:
    meta = review_event_metadata(
        thread_id="wf-1",
        action="approve",
        edited_content="raw draft body",  # disallowed
        reason="reviewer comment",  # disallowed
        status=None,  # dropped because None
    )
    assert meta == {"thread_id": "wf-1", "action": "approve"}
    assert "edited_content" not in meta
    assert "reason" not in meta
