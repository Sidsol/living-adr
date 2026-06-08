"""Phase 3: the webhook route schedules drafting off-request on accept (202).

An accepted merged-PR delivery with an attached SCMEvent schedules the injected
draft scheduler via FastAPI background tasks; non-accepted outcomes never
schedule drafting.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.workflow.orchestration.fixtures import make_event

from living_adr.apps.workflow_service.asgi import WEBHOOK_PATH, create_webhook_app
from living_adr.apps.workflow_service.webhooks import (
    GitHubWebhookHandler,
    WebhookResponse,
)
from living_adr.scm.github_webhook import compute_signature

SECRET = "test-webhook-secret"  # noqa: S105 - test fixture, not a real secret


class _FakePipeline:
    def __init__(self, response: WebhookResponse) -> None:
        self._response = response

    def process(self, raw_body: bytes, headers: object) -> WebhookResponse:
        return self._response


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[str, ...]]] = []

    def __call__(self, event: object, refs: tuple[str, ...]) -> None:
        self.calls.append((event, refs))


def _client(response: WebhookResponse, scheduler: _Recorder) -> TestClient:
    handler = GitHubWebhookHandler(secret=SECRET, pipeline=_FakePipeline(response))
    app = create_webhook_app(handler=handler, draft_scheduler=scheduler)
    return TestClient(app)


def _post(client: TestClient, body: bytes = b'{"x":1}'):
    return client.post(
        WEBHOOK_PATH,
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "d1",
            "X-Hub-Signature-256": compute_signature(SECRET, body),
        },
    )


def test_accepted_delivery_schedules_drafting() -> None:
    event = make_event()
    scheduler = _Recorder()
    response = WebhookResponse(
        status_code=202,
        outcome="accepted",
        delivery_id="d1",
        scm_event=event,
        evidence_refs=("pr-key-1",),
    )

    result = _post(_client(response, scheduler))

    assert result.status_code == 202
    assert len(scheduler.calls) == 1
    assert scheduler.calls[0][1] == ("pr-key-1",)


def test_skipped_delivery_does_not_schedule_drafting() -> None:
    scheduler = _Recorder()
    response = WebhookResponse(
        status_code=200, outcome="skipped", delivery_id="d1"
    )

    result = _post(_client(response, scheduler))

    assert result.status_code == 200
    assert scheduler.calls == []
