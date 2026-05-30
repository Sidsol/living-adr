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
    RETRYABLE_CATEGORIES,
    DeliveryStatus,
    IngestionDelivery,
    IngestionErrorCategory,
)
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.scm import (
    CandidateEvidence,
    SCMEventEnvelope,
    SCMProvider,
    SCMProviderError,
    category_for_error,
)
from living_adr.persistence.ingestion_store import IngestionStore
from living_adr.scm.github_webhook import (
    FilterDecision,
    FilterResult,
    WebhookHeaders,
    normalize_to_scm_event,
    parse_and_filter,
)

# Decision -> (delivery status, HTTP-ish status code, outcome label).
_DECISION_MAP: dict[FilterDecision, tuple[DeliveryStatus, int, str]] = {
    FilterDecision.ACCEPT: (DeliveryStatus.ACCEPTED, 202, "accepted"),
    FilterDecision.SKIP: (DeliveryStatus.SKIPPED, 200, "skipped"),
    FilterDecision.REJECT: (DeliveryStatus.REJECTED, 422, "rejected"),
}


class EvidenceBuilder:
    """Builds immutable candidate evidence from a normalized event envelope.

    Reuses cached evidence keyed by the normalized PR key so idempotent retries
    and replays do not re-call the provider (NFR-3, FM-18). Provider failures
    propagate and emit *no* partial evidence.
    """

    def __init__(
        self,
        provider: SCMProvider,
        store: IngestionStore,
        observability: Observability | None = None,
    ) -> None:
        self._provider = provider
        self._store = store
        self._obs: Observability = observability or NoOpObservability()

    def build(self, envelope: SCMEventEnvelope) -> CandidateEvidence:
        cached = self._store.get_evidence(envelope.normalized_pr_key)
        if cached is not None:
            self._obs.increment_counter(
                "ingestion.evidence_cache_hit",
                metadata={"normalized_pr_key": envelope.normalized_pr_key},
            )
            return cached

        repository = envelope.event.repository
        handle = envelope.fetch_handle
        pr = self._provider.fetch_pull_request(repository, handle)
        changed_files = self._provider.fetch_changed_files(repository, handle)
        diff = self._provider.fetch_diff(repository, handle)

        evidence = CandidateEvidence(
            repository=repository,
            source_delivery_id=envelope.event.delivery_id,
            normalized_pr_key=envelope.normalized_pr_key,
            pr_number=pr.number,
            pr_title=pr.title,
            changed_files=changed_files,
            diff=diff,
            provider=envelope.provider,
        )
        stored = self._store.put_evidence(evidence)
        self._obs.record_event(
            "ingestion.evidence_built",
            {
                "normalized_pr_key": envelope.normalized_pr_key,
                "changed_file_count": len(changed_files),
            },
        )
        return stored


class IngestionPipeline:
    """Verified-request processing seam with delivery-id idempotency."""

    def __init__(
        self,
        config: LivingADRConfig,
        store: IngestionStore,
        provider: SCMProvider | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._provider = provider
        self._obs: Observability = observability or NoOpObservability()
        self._evidence_builder = (
            EvidenceBuilder(provider, store, self._obs)
            if provider is not None
            else None
        )

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

        if (
            result.decision is FilterDecision.ACCEPT
            and self._evidence_builder is not None
            and result.repository is not None
            and result.payload is not None
        ):
            return self._accept_with_evidence(delivery_id, result)

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

    def _accept_with_evidence(
        self, delivery_id: str, result: FilterResult
    ) -> WebhookResponse:
        """Normalize an accepted delivery and collect candidate evidence.

        Provider failures transition the delivery to a retryable or dead-letter
        state with a structured error category; no complete evidence is emitted.
        """

        assert result.repository is not None and result.payload is not None
        envelope = normalize_to_scm_event(
            delivery_id, result.repository, result.payload
        )
        assert self._evidence_builder is not None
        try:
            self._evidence_builder.build(envelope)
        except SCMProviderError as exc:
            category = category_for_error(exc)
            retryable = category in RETRYABLE_CATEGORIES
            status = (
                DeliveryStatus.RETRYABLE if retryable else DeliveryStatus.FAILED
            )
            delivery = IngestionDelivery(
                delivery_id=delivery_id,
                status=status,
                error_category=category,
                repository_key=result.repository.key,
                normalized_pr_key=envelope.normalized_pr_key,
                pr_number=result.payload.pr_number,
                detail=str(exc),
            )
            self._store.upsert_delivery(delivery)
            self._obs.record_event(
                "ingestion.fetch_failed",
                {
                    "delivery_id": delivery_id,
                    "error_category": category.value,
                    "retryable": retryable,
                },
            )
            return WebhookResponse(
                status_code=503 if retryable else 502,
                outcome="fetch_failed",
                delivery_id=delivery_id,
                detail=category.value,
            )

        delivery = IngestionDelivery(
            delivery_id=delivery_id,
            status=DeliveryStatus.ACCEPTED,
            error_category=IngestionErrorCategory.NONE,
            repository_key=result.repository.key,
            normalized_pr_key=envelope.normalized_pr_key,
            pr_number=result.payload.pr_number,
        )
        self._store.upsert_delivery(delivery)
        self._obs.record_event(
            "ingestion.accepted",
            {
                "delivery_id": delivery_id,
                "normalized_pr_key": envelope.normalized_pr_key,
                "repository_key": result.repository.key,
            },
        )
        return WebhookResponse(
            status_code=202,
            outcome="accepted",
            delivery_id=delivery_id,
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


__all__ = ["IngestionPipeline", "EvidenceBuilder"]
