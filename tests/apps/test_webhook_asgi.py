"""HTTP/ASGI surface for the workflow-service GitHub webhook receiver.

These tests cover only the thin transport adapter: it must read the *raw* request
bytes, pass headers to the already-tested :class:`GitHubWebhookHandler`, and map
the resulting :class:`WebhookResponse` to an HTTP response without leaking secrets
or raw payloads. Verification/idempotency/filtering live in tested seams below it.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from living_adr.apps.workflow_service.asgi import WEBHOOK_PATH, create_webhook_app
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

SECRET = "asgi-endpoint-secret"
RAW_BODY = b'{"action":"closed","pull_request":{"merged":true}}'


def _sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@dataclass
class SpyPipeline:
    """Records downstream invocations to prove the transport wiring."""

    calls: list[WebhookHeaders] = field(default_factory=list)
    response: WebhookResponse = field(
        default_factory=lambda: WebhookResponse(
            status_code=202, outcome="accepted", delivery_id="delivery-1"
        )
    )

    def process(
        self, raw_body: bytes, headers: WebhookHeaders
    ) -> WebhookResponse:
        self.calls.append(headers)
        return self.response


def _headers(signature: str | None) -> dict[str, str]:
    headers = {DELIVERY_HEADER: "delivery-1", EVENT_HEADER: "pull_request"}
    if signature is not None:
        headers[SIGNATURE_HEADER] = signature
    return headers


def _client(pipeline: SpyPipeline) -> TestClient:
    handler = GitHubWebhookHandler(secret=SECRET, pipeline=pipeline)
    return TestClient(create_webhook_app(handler=handler))


def test_healthz_reports_ok() -> None:
    client = _client(SpyPipeline())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_signed_delivery_reaches_pipeline_and_maps_status() -> None:
    pipeline = SpyPipeline()
    client = _client(pipeline)
    response = client.post(
        WEBHOOK_PATH, content=RAW_BODY, headers=_headers(_sign(RAW_BODY))
    )
    assert len(pipeline.calls) == 1
    assert pipeline.calls[0].delivery_id == "delivery-1"
    assert response.status_code == 202
    body = response.json()
    assert body["outcome"] == "accepted"
    assert body["delivery_id"] == "delivery-1"


def test_raw_bytes_are_verified_not_reserialized_json() -> None:
    # Body with insignificant whitespace: HMAC is over the exact bytes received,
    # so the transport must not re-serialize before verifying.
    raw = b'{"action":"closed",  "pull_request":{"merged":true}}'
    pipeline = SpyPipeline()
    client = _client(pipeline)
    response = client.post(
        WEBHOOK_PATH, content=raw, headers=_headers(_sign(raw))
    )
    assert response.status_code == 202
    assert len(pipeline.calls) == 1


def test_bad_signature_returns_401_and_skips_pipeline() -> None:
    pipeline = SpyPipeline()
    client = _client(pipeline)
    response = client.post(
        WEBHOOK_PATH,
        content=RAW_BODY,
        headers=_headers(_sign(RAW_BODY, "wrong-secret")),
    )
    assert response.status_code == 401
    assert pipeline.calls == []


def test_missing_delivery_header_returns_400() -> None:
    pipeline = SpyPipeline()
    client = _client(pipeline)
    headers = {EVENT_HEADER: "pull_request", SIGNATURE_HEADER: _sign(RAW_BODY)}
    response = client.post(WEBHOOK_PATH, content=RAW_BODY, headers=headers)
    assert response.status_code == 400
    assert pipeline.calls == []


def test_response_body_is_metadata_only() -> None:
    pipeline = SpyPipeline()
    client = _client(pipeline)
    response = client.post(
        WEBHOOK_PATH,
        content=RAW_BODY,
        headers=_headers(_sign(RAW_BODY, "wrong-secret")),
    )
    text = response.text
    assert SECRET not in text
    assert "merged" not in text
