"""FastAPI HITL review routes for the workflow-service (feature 009).

Server-rendered, accessible review surface that plugs into feature 015's
interrupt/resume seam through :class:`ReviewWorkflowGateway`. This module owns the
HTTP/UI surface only:

* ``GET /hitl/reviews`` — metadata-only pending list.
* ``GET /hitl/reviews/{thread_id}`` — accessible draft + evidence review page.
* ``POST /hitl/reviews/{thread_id}/submit`` — validate and submit a typed
  ``ReviewResumeCommand`` (approve / approve_after_edit / reject / defer), then
  redirect (post/redirect/get) to a status page.
* ``GET /hitl/reviews/{thread_id}/status`` — terminal status / error states.

Boundaries (architecture #service-boundaries, #anti-patterns): it mints no
approval capability (feature 010), performs no graph mutation, and calls neither
Claude nor GitHub. All telemetry is metadata-only.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.hitl.gateway import ReviewWorkflowGateway
from living_adr.hitl.models import page_model_from_payload

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "hitl"
_STATIC_DIR = Path(__file__).parent / "static"

DEFAULT_REVIEWER_ID = "poc-reviewer"


def _build_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=False,
        lstrip_blocks=False,
    )


def create_hitl_app(
    *,
    gateway: ReviewWorkflowGateway,
    reviewer_id: str = DEFAULT_REVIEWER_ID,
    ui_token: str | None = None,
    nonce_secret: str = "dev-nonce-secret",
    observability: Observability | None = None,
) -> FastAPI:
    """Assemble the HITL review FastAPI app bound to a review gateway."""

    env = _build_environment()
    obs: Observability = observability or NoOpObservability()
    app = FastAPI(title="LivingADR HITL Review", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    def _render(template_name: str, **context: object) -> str:
        return env.get_template(template_name).render(**context)

    def _not_found() -> HTMLResponse:
        html = _render(
            "status.html",
            state="not_found",
            heading="Review not found",
            message=(
                "No pending review exists for this thread. It may have expired, "
                "already been actioned, or never existed."
            ),
            action_label=None,
            outcome_status=None,
        )
        return HTMLResponse(html, status_code=404)

    @app.get("/hitl/reviews", response_class=HTMLResponse)
    def list_reviews() -> HTMLResponse:
        summaries = gateway.list_pending()
        obs.record_event("hitl.review.list", {"pending_count": len(summaries)})
        return HTMLResponse(_render("index.html", summaries=summaries))

    @app.get("/hitl/reviews/{thread_id}", response_class=HTMLResponse)
    def review_page(thread_id: str) -> HTMLResponse:
        payload = gateway.get_pending_review(thread_id)
        if payload is None:
            obs.record_event(
                "hitl.review.view", {"thread_id": thread_id, "result": "not_found"}
            )
            return _not_found()
        page = page_model_from_payload(payload, thread_id=thread_id)
        obs.record_event(
            "hitl.review.view",
            {
                "thread_id": thread_id,
                "repository": page.repository_key,
                "result": "ok",
            },
        )
        html = _render(
            "review.html",
            page=page,
            reviewer_id=reviewer_id,
            nonce="",
            errors=(),
            field_errors={},
            edited_content="",
            reason="",
        )
        return HTMLResponse(html)

    # POST submit and status routes are added by later slices on this same app.
    return app


__all__ = ["create_hitl_app", "DEFAULT_REVIEWER_ID"]
