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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from living_adr.apps.workflow_service.webhooks import GitHubWebhookHandler

WEBHOOK_PATH = "/webhooks/github"


def create_webhook_app(*, handler: GitHubWebhookHandler) -> FastAPI:
    """Assemble the webhook-receiver FastAPI app bound to a verified handler."""

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
    async def receive_github_webhook(request: Request) -> JSONResponse:
        # Read the exact bytes GitHub signed; the handler verifies the HMAC over
        # these raw bytes before any downstream side effect. handler.handle is
        # fully synchronous and is invoked inline on the event-loop thread, so
        # the single SQLite connection in the pipeline is never crossed between
        # threads. Do not wrap this in a threadpool without revisiting that.
        raw_body = await request.body()
        result = handler.handle(raw_body, dict(request.headers))

        body: dict[str, str] = {"outcome": result.outcome}
        if result.delivery_id is not None:
            body["delivery_id"] = result.delivery_id
        if result.detail is not None:
            body["detail"] = result.detail
        return JSONResponse(body, status_code=result.status_code)

    return app


__all__ = ["create_webhook_app", "WEBHOOK_PATH"]
