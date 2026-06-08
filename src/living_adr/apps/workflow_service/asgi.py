"""HTTP/ASGI surface for the workflow-service GitHub webhook receiver.

This is the thin transport adapter the ``living-adr-workflow`` deployable runs
under uvicorn. It owns *only* the HTTP boundary: read the raw request bytes, pass
them with the headers to the already-tested :class:`GitHubWebhookHandler` (which
enforces the HMAC trust boundary), and map the returned :class:`WebhookResponse`
to an HTTP response. All verification, idempotency, and filtering live in the
injected handler/pipeline seams; no GitHub, LLM, or graph calls happen here.

Responses are metadata-only (architecture #cross-cutting, NFR-6): the JSON body
carries the outcome label, delivery id, and a safe detail string — never the raw
payload, diff, or secret.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from living_adr.apps.workflow_service.webhooks import GitHubWebhookHandler

if TYPE_CHECKING:
    from collections.abc import Callable

    from living_adr.core.models import SCMEvent

    #: Schedules the off-request drafting run for an accepted merged PR.
    DraftScheduler = Callable[[SCMEvent, tuple[str, ...]], None]

WEBHOOK_PATH = "/webhooks/github"


def create_webhook_app(
    *,
    handler: GitHubWebhookHandler,
    draft_scheduler: DraftScheduler | None = None,
    hitl_app: FastAPI | None = None,
) -> FastAPI:
    """Assemble the webhook-receiver FastAPI app bound to a verified handler.

    When ``draft_scheduler`` is provided, an accepted (202) merged-PR delivery
    schedules the drafting graph to run **after** the response is returned, via
    FastAPI background tasks (off the request path), so the webhook stays fast
    while the slower Claude drafting runs in a worker thread. When ``hitl_app`` is
    provided, the human review UI is mounted on the same app/port (its
    ``/hitl/...`` and ``/static`` routes do not collide with the receiver's
    ``/healthz`` and ``/webhooks/github`` routes, which are matched first).
    """

    app = FastAPI(
        title="LivingADR Workflow Service",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness/readiness probe for tunnels and orchestrators."""

        return {"status": "ok"}

    @app.post(WEBHOOK_PATH)
    async def receive_github_webhook(
        request: Request, background_tasks: BackgroundTasks
    ) -> JSONResponse:
        # Read the exact bytes GitHub signed; the handler verifies the HMAC over
        # these raw bytes before any downstream side effect. handler.handle is
        # fully synchronous and is invoked inline on the event-loop thread, so
        # the single SQLite connection in the pipeline is never crossed between
        # threads. Do not wrap this in a threadpool without revisiting that.
        raw_body = await request.body()
        result = handler.handle(raw_body, dict(request.headers))

        # Accepted merged PR: hand drafting to a background task so the slow
        # Claude call never blocks the webhook response (GitHub times out fast).
        if (
            draft_scheduler is not None
            and result.status_code == 202
            and result.scm_event is not None
        ):
            background_tasks.add_task(
                draft_scheduler, result.scm_event, result.evidence_refs
            )

        body: dict[str, str] = {"outcome": result.outcome}
        if result.delivery_id is not None:
            body["delivery_id"] = result.delivery_id
        if result.detail is not None:
            body["detail"] = result.detail
        return JSONResponse(body, status_code=result.status_code)

    if hitl_app is not None:
        # Mount last so the receiver's explicit routes above match first; the
        # HITL UI handles /hitl/... and /static.
        app.mount("/", hitl_app)

    return app


__all__ = ["create_webhook_app", "WEBHOOK_PATH"]
