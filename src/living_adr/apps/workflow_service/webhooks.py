"""workflow-service GitHub webhook handler (feature 003).

The handler is intentionally thin: it enforces the trust boundary (required
headers + raw-body HMAC) and then delegates verified requests to an injected
:class:`WebhookPipeline`. Later slices supply the real pipeline (idempotency,
filtering, normalization, evidence). A spoofed or malformed request is rejected
here and never reaches the store, provider, or normalizer.

All responses and observations are metadata-only (architecture #cross-cutting,
NFR-6): no raw bodies, diffs, or secrets are returned or recorded.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.scm.github_webhook import (
    MissingHeaderError,
    WebhookHeaders,
    extract_headers,
    verify_signature,
)


@dataclass(frozen=True)
class WebhookResponse:
    """Metadata-only result of handling a webhook delivery."""

    status_code: int
    outcome: str
    delivery_id: str | None = None
    detail: str | None = None


class WebhookPipeline(Protocol):
    """Downstream seam invoked only after signature + header verification."""

    def process(
        self, raw_body: bytes, headers: WebhookHeaders
    ) -> WebhookResponse: ...


class GitHubWebhookHandler:
    """Verifies GitHub webhook authenticity before delegating downstream."""

    def __init__(
        self,
        secret: str,
        pipeline: WebhookPipeline | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._secret = secret
        self._pipeline = pipeline
        self._obs: Observability = observability or NoOpObservability()

    def handle(
        self, raw_body: bytes, headers: Mapping[str, str]
    ) -> WebhookResponse:
        """Reject unauthenticated requests; delegate verified ones downstream."""

        try:
            extracted = extract_headers(headers)
        except MissingHeaderError as exc:
            self._obs.record_event(
                "webhook.rejected",
                {"reason": "missing_headers", "error": str(exc)},
            )
            return WebhookResponse(
                status_code=400,
                outcome="rejected_missing_headers",
                detail=str(exc),
            )

        if not verify_signature(self._secret, raw_body, extracted.signature):
            self._obs.record_event(
                "webhook.rejected",
                {
                    "reason": "invalid_signature",
                    "event": extracted.event_name,
                    "delivery_id": extracted.delivery_id,
                    "signature_present": extracted.signature is not None,
                },
            )
            return WebhookResponse(
                status_code=401,
                outcome="rejected_invalid_signature",
                delivery_id=extracted.delivery_id,
            )

        self._obs.record_event(
            "webhook.verified",
            {"event": extracted.event_name, "delivery_id": extracted.delivery_id},
        )
        if self._pipeline is None:
            return WebhookResponse(
                status_code=202,
                outcome="verified",
                delivery_id=extracted.delivery_id,
            )
        return self._pipeline.process(raw_body, extracted)
