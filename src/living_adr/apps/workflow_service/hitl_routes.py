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
from types import SimpleNamespace

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.hitl.auth import NonceSigner, UITokenGuard
from living_adr.hitl.gateway import ReviewWorkflowGateway
from living_adr.hitl.hashing import compute_edited_draft_hash
from living_adr.hitl.models import page_model_from_payload, validate_edited_draft
from living_adr.hitl.observability import emit_review_event
from living_adr.workflow.state import ReviewAction, ReviewResumeCommand

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "hitl"
_STATIC_DIR = Path(__file__).parent / "static"

DEFAULT_REVIEWER_ID = "poc-reviewer"
UI_TOKEN_HEADER = "X-UI-Token"


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
    token_guard = UITokenGuard(ui_token)
    nonce_signer = NonceSigner(nonce_secret)
    app = FastAPI(title="LivingADR HITL Review", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    def _render(template_name: str, **context: object) -> str:
        return env.get_template(template_name).render(**context)

    def _authorized(request: Request) -> bool:
        return token_guard.is_authorized(request.headers.get(UI_TOKEN_HEADER))

    def _unauthorized() -> HTMLResponse:
        html = _render(
            "status.html",
            state="unauthorized",
            heading="Access denied",
            message=(
                "A valid local UI token is required to view or action reviews."
            ),
            action_label=None,
            outcome_status=None,
        )
        return HTMLResponse(html, status_code=401)

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

    def _render_review(
        thread_id: str,
        page,
        *,
        status_code: int = 200,
        field_errors: dict[str, str] | None = None,
        errors: tuple = (),
        edited_content: str = "",
        reason: str = "",
    ) -> HTMLResponse:
        field_errors = field_errors or {}
        if field_errors and not errors:
            errors = tuple(
                SimpleNamespace(field=field, message=message)
                for field, message in field_errors.items()
            )
        html = _render(
            "review.html",
            page=page,
            reviewer_id=reviewer_id,
            nonce=nonce_signer.issue(thread_id, page.draft_content_hash),
            errors=errors,
            field_errors=field_errors,
            edited_content=edited_content,
            reason=reason,
        )
        return HTMLResponse(html, status_code=status_code)

    @app.get("/hitl/reviews", response_class=HTMLResponse)
    def list_reviews(request: Request) -> HTMLResponse:
        if not _authorized(request):
            return _unauthorized()
        summaries = gateway.list_pending()
        emit_review_event(
            obs, "hitl.review.list", pending_count=len(summaries)
        )
        return HTMLResponse(_render("index.html", summaries=summaries))

    @app.get("/hitl/reviews/{thread_id}", response_class=HTMLResponse)
    def review_page(request: Request, thread_id: str) -> HTMLResponse:
        if not _authorized(request):
            return _unauthorized()
        payload = gateway.get_pending_review(thread_id)
        if payload is None:
            emit_review_event(
                obs, "hitl.review.view", thread_id=thread_id, result="not_found"
            )
            return _not_found()
        page = page_model_from_payload(payload, thread_id=thread_id)
        emit_review_event(
            obs,
            "hitl.review.view",
            thread_id=thread_id,
            repository=page.repository_key,
            result="ok",
        )
        return _render_review(thread_id, page)

    @app.get("/hitl/reviews/{thread_id}/status", response_class=HTMLResponse)
    def review_status(
        request: Request, thread_id: str, action: str = "", status: str = ""
    ) -> HTMLResponse:
        if not _authorized(request):
            return _unauthorized()
        html = _render(
            "status.html",
            state="submitted",
            heading="Decision recorded",
            message=(
                "Your review decision was submitted and the workflow was "
                "resumed. No ADR was published and no approval capability was "
                "minted by this step."
            ),
            action_label=action.replace("_", " ") or None,
            outcome_status=status or None,
        )
        return HTMLResponse(html)

    @app.post("/hitl/reviews/{thread_id}/submit")
    def submit_review(
        request: Request,
        thread_id: str,
        action: str = Form(...),
        nonce: str = Form(""),
        draft_content_hash: str = Form(""),
        edited_content: str = Form(""),
        reason: str = Form(""),
    ):
        if not _authorized(request):
            return _unauthorized()

        payload = gateway.get_pending_review(thread_id)
        if payload is None:
            return _not_found()
        page = page_model_from_payload(payload, thread_id=thread_id)

        # CSRF/replay guard: nonce must bind this thread + the reviewed hash.
        if not nonce_signer.verify(nonce, thread_id, page.draft_content_hash):
            emit_review_event(
                obs, "hitl.review.submit", thread_id=thread_id, result="bad_nonce"
            )
            return HTMLResponse("Invalid or expired form token.", status_code=400)

        try:
            review_action = ReviewAction(action)
        except ValueError:
            return HTMLResponse("Unknown review action.", status_code=400)

        if review_action is ReviewAction.REJECT and not reason.strip():
            return _render_review(
                thread_id,
                page,
                status_code=400,
                field_errors={"reason": "A reason is required to reject a draft."},
                reason=reason,
            )

        edited: str | None = None
        edited_hash: str | None = None
        if review_action is ReviewAction.APPROVE_AFTER_EDIT:
            validation = validate_edited_draft(edited_content)
            if not validation.ok:
                return _render_review(
                    thread_id,
                    page,
                    status_code=400,
                    field_errors={
                        "edited_content": "; ".join(
                            e.message for e in validation.errors
                        )
                    },
                    edited_content=validation.normalized_content,
                )
            edited = validation.normalized_content
            edited_hash = compute_edited_draft_hash(edited)

        command = ReviewResumeCommand(
            action=review_action,
            reviewer_id=reviewer_id,
            edited_content=edited,
            edited_content_hash=edited_hash,
        )
        outcome = gateway.submit_resume(thread_id, command)
        # Metadata-only: action + status enums, never the reason/comment text.
        emit_review_event(
            obs,
            "hitl.review.submit",
            thread_id=thread_id,
            action=review_action.value,
            result="submitted",
            status=getattr(outcome.status, "value", None),
        )
        location = (
            f"/hitl/reviews/{thread_id}/status"
            f"?action={review_action.value}"
            f"&status={getattr(outcome.status, 'value', '')}"
        )
        return RedirectResponse(location, status_code=303)

    return app


__all__ = ["create_hitl_app", "DEFAULT_REVIEWER_ID"]
