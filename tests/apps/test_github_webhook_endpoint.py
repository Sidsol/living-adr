"""Slice 1 RED tests: thin webhook handler rejects before any side effects.

Asserts the handler verifies the HMAC signature (over raw bytes) and required
headers *before* invoking the downstream pipeline seam, so a spoofed or malformed
request can never reach the store, provider, or normalizer.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field

from living_adr.apps.workflow_service.webhooks import (
    GitHubWebhookHandler,
    WebhookResponse,
)
from living_adr.scm.github_webhook import (
    DELIVERY_HEADER,
    EVENT_HEADER,
    SIGNATURE_HEADER,
    WebhookHeaders,
)

SECRET = "endpoint-secret"
RAW_BODY = b'{"action":"closed","pull_request":{"merged":true}}'


def _sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@dataclass
class SpyPipeline:
    """Records downstream invocations so we can prove no side effects occur."""

    calls: list[WebhookHeaders] = field(default_factory=list)
    response: WebhookResponse = field(
        default_factory=lambda: WebhookResponse(
            status_code=202, outcome="accepted", delivery_id="d"
        )
    )

    def process(self, raw_body: bytes, headers: WebhookHeaders) -> WebhookResponse:
        self.calls.append(headers)
        return self.response


def _headers(signature: str | None) -> dict[str, str]:
    headers = {DELIVERY_HEADER: "delivery-1", EVENT_HEADER: "pull_request"}
    if signature is not None:
        headers[SIGNATURE_HEADER] = signature
    return headers


def test_valid_signature_reaches_pipeline() -> None:
    pipeline = SpyPipeline()
    handler = GitHubWebhookHandler(secret=SECRET, pipeline=pipeline)
    response = handler.handle(RAW_BODY, _headers(_sign(RAW_BODY)))
    assert len(pipeline.calls) == 1
    assert pipeline.calls[0].delivery_id == "delivery-1"
    assert response.status_code == 202


def test_invalid_signature_does_not_reach_pipeline() -> None:
    pipeline = SpyPipeline()
    handler = GitHubWebhookHandler(secret=SECRET, pipeline=pipeline)
    response = handler.handle(RAW_BODY, _headers(_sign(RAW_BODY, "wrong")))
    assert pipeline.calls == []
    assert response.status_code == 401
    assert "signature" in response.outcome
    assert response.delivery_id == "delivery-1"


def test_tampered_body_does_not_reach_pipeline() -> None:
    pipeline = SpyPipeline()
    handler = GitHubWebhookHandler(secret=SECRET, pipeline=pipeline)
    signature = _sign(RAW_BODY)
    response = handler.handle(RAW_BODY + b"x", _headers(signature))
    assert pipeline.calls == []
    assert response.status_code == 401


def test_missing_signature_header_rejected() -> None:
    pipeline = SpyPipeline()
    handler = GitHubWebhookHandler(secret=SECRET, pipeline=pipeline)
    response = handler.handle(RAW_BODY, _headers(None))
    assert pipeline.calls == []
    assert response.status_code == 401


def test_missing_delivery_id_rejected_before_signature() -> None:
    pipeline = SpyPipeline()
    handler = GitHubWebhookHandler(secret=SECRET, pipeline=pipeline)
    headers = {EVENT_HEADER: "pull_request", SIGNATURE_HEADER: _sign(RAW_BODY)}
    response = handler.handle(RAW_BODY, headers)
    assert pipeline.calls == []
    assert response.status_code == 400


class RecordingObservability:
    """Captures metadata-only observations for hygiene assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def record_event(self, name: str, metadata=None) -> None:
        self.events.append((name, dict(metadata or {})))

    def increment_counter(self, name, value=1, metadata=None) -> None:
        self.events.append((name, dict(metadata or {})))

    def start_span(self, name, metadata=None):  # pragma: no cover - unused here
        from contextlib import nullcontext

        return nullcontext()


def test_rejection_emits_metadata_only_observability() -> None:
    obs = RecordingObservability()
    handler = GitHubWebhookHandler(
        secret=SECRET, pipeline=SpyPipeline(), observability=obs
    )
    handler.handle(RAW_BODY, _headers(_sign(RAW_BODY, "wrong")))
    assert obs.events, "rejection should be observed"
    # No raw body / secret content leaks into metadata.
    for _name, metadata in obs.events:
        serialized = repr(metadata)
        assert SECRET not in serialized
        assert "pull_request" not in serialized or "event" in metadata
        assert b"merged".decode() not in str(metadata.get("body", ""))
