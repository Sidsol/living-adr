"""Ingestion pipeline: idempotency, filtering, normalization, evidence handoff.

The pipeline is the verified-request seam invoked by
:class:`~living_adr.apps.workflow_service.webhooks.GitHubWebhookHandler` after the
HMAC trust boundary. It is provider-agnostic at the orchestration level: GitHub
specifics live in :mod:`living_adr.scm.github_webhook` and the injected
``SCMProvider`` adapter.

Slice 2 establishes idempotency + filtering + delivery-state persistence. Later
slices extend :meth:`IngestionPipeline.process` with normalization (slice 3),
candidate-evidence collection (slice 4), and metadata-only observability (slice 6).
"""

from __future__ import annotations

from living_adr.apps.workflow_service.webhooks import WebhookResponse
from living_adr.core.config import LivingADRConfig
from living_adr.core.ingestion import (
    DeliveryStatus,
    IngestionDelivery,
    IngestionErrorCategory,
)
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.persistence.ingestion_store import IngestionStore
from living_adr.scm.github_webhook import (
    FilterDecision,
    FilterResult,
    WebhookHeaders,
    parse_and_filter,
)

# Decision -> (delivery status, HTTP-ish status code, outcome label).
_DECISION_MAP: dict[FilterDecision, tuple[DeliveryStatus, int, str]] = {
    FilterDecision.ACCEPT: (DeliveryStatus.ACCEPTED, 202, "accepted"),
    FilterDecision.SKIP: (DeliveryStatus.SKIPPED, 200, "skipped"),
    FilterDecision.REJECT: (DeliveryStatus.REJECTED, 422, "rejected"),
}


class IngestionPipeline:
    """Verified-request processing seam with delivery-id idempotency."""

    def __init__(
        self,
        config: LivingADRConfig,
        store: IngestionStore,
        observability: Observability | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._obs: Observability = observability or NoOpObservability()

    def process(
        self, raw_body: bytes, headers: WebhookHeaders
    ) -> WebhookResponse:
        delivery_id = headers.delivery_id

        existing = self._store.get_delivery(delivery_id)
        if existing is not None:
            self._obs.record_event(
                "ingestion.duplicate",
                {
                    "delivery_id": delivery_id,
                    "prior_status": existing.status.value,
                },
            )
            return WebhookResponse(
                status_code=200,
                outcome="duplicate",
                delivery_id=delivery_id,
                detail=f"prior status {existing.status.value}",
            )

        result = parse_and_filter(raw_body, headers.event_name, self._config)
        delivery = self._delivery_from_result(delivery_id, result)
        self._store.upsert_delivery(delivery)

        status_code, outcome = self._response_meta(result.decision)
        self._obs.record_event(
            "ingestion.processed",
            {
                "delivery_id": delivery_id,
                "decision": result.decision.value,
                "error_category": result.error_category.value,
                "repository_key": delivery.repository_key,
            },
        )
        return WebhookResponse(
            status_code=status_code,
            outcome=outcome,
            delivery_id=delivery_id,
            detail=result.detail,
        )

    def _delivery_from_result(
        self, delivery_id: str, result: FilterResult
    ) -> IngestionDelivery:
        status, _code, _label = _DECISION_MAP[result.decision]
        repository_key = result.repository.key if result.repository else None
        pr_number = result.payload.pr_number if result.payload else None
        return IngestionDelivery(
            delivery_id=delivery_id,
            status=status,
            error_category=result.error_category or IngestionErrorCategory.NONE,
            repository_key=repository_key,
            pr_number=pr_number,
            detail=result.detail,
        )

    @staticmethod
    def _response_meta(decision: FilterDecision) -> tuple[int, str]:
        _status, code, label = _DECISION_MAP[decision]
        return code, label


__all__ = ["IngestionPipeline"]
