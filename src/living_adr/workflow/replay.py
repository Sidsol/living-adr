"""Replay + dead-letter recovery service (feature 003, slice 5).

Reprocesses *stored* deliveries without requiring GitHub to resend a webhook
(FM-17). Replay preserves idempotency: an already-accepted event reuses its cached
candidate evidence (no provider refetch, no duplicate ``SCMEvent``/evidence), and
a previously failed fetch is retried against the stored normalized envelope. Retry
budgets and non-retryable (poison) categories escalate to a terminal dead-letter
state with structured error metadata for operator triage.
"""

from __future__ import annotations

from dataclasses import dataclass

from living_adr.core.ingestion import (
    DEFAULT_MAX_RETRIES,
    DeliveryStatus,
    IngestionDelivery,
    IngestionErrorCategory,
    classify_failure,
)
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.scm import (
    CandidateEvidence,
    SCMProvider,
    SCMProviderError,
    category_for_error,
)
from living_adr.persistence.ingestion_store import IngestionStore
from living_adr.workflow.ingestion import EvidenceBuilder


@dataclass(frozen=True)
class ReplayResult:
    """Outcome of replaying one stored delivery."""

    delivery: IngestionDelivery | None
    evidence: CandidateEvidence | None
    reused: bool
    status: DeliveryStatus | None


class ReplayService:
    """Operator-facing replay over stored delivery/envelope/evidence records."""

    def __init__(
        self,
        store: IngestionStore,
        provider: SCMProvider,
        observability: Observability | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._store = store
        self._obs: Observability = observability or NoOpObservability()
        self._max_retries = max_retries
        self._builder = EvidenceBuilder(provider, store, self._obs)

    def replay_delivery(self, delivery_id: str) -> ReplayResult:
        delivery = self._store.get_delivery(delivery_id)
        if delivery is None:
            self._obs.record_event(
                "ingestion.replay_missing", {"delivery_id": delivery_id}
            )
            return ReplayResult(
                delivery=None, evidence=None, reused=False, status=None
            )

        envelope = self._store.get_envelope(delivery_id)
        if envelope is None:
            # No normalized envelope was ever stored (e.g. skipped/rejected
            # before normalization); there is nothing to reprocess.
            self._obs.record_event(
                "ingestion.replay_not_reprocessable",
                {"delivery_id": delivery_id, "status": delivery.status.value},
            )
            return ReplayResult(
                delivery=delivery,
                evidence=None,
                reused=False,
                status=delivery.status,
            )

        # Idempotent fast path: evidence already exists -> reuse, no refetch.
        existing = self._store.get_evidence(envelope.normalized_pr_key)
        if existing is not None:
            updated = delivery.with_status(
                DeliveryStatus.REPLAYED,
                error_category=IngestionErrorCategory.NONE,
            )
            self._store.upsert_delivery(updated)
            self._obs.record_event(
                "ingestion.replayed_reused",
                {
                    "delivery_id": delivery_id,
                    "normalized_pr_key": envelope.normalized_pr_key,
                },
            )
            return ReplayResult(
                delivery=updated,
                evidence=existing,
                reused=True,
                status=DeliveryStatus.REPLAYED,
            )

        # Re-attempt the provider fetch against the stored envelope.
        try:
            evidence = self._builder.build(envelope)
        except SCMProviderError as exc:
            category = category_for_error(exc)
            new_retry = delivery.retry_count + 1
            status = classify_failure(category, new_retry, self._max_retries)
            updated = delivery.model_copy(
                update={
                    "status": status,
                    "error_category": category,
                    "retry_count": new_retry,
                    "detail": str(exc),
                }
            )
            self._store.upsert_delivery(updated)
            self._obs.record_event(
                "ingestion.replay_failed",
                {
                    "delivery_id": delivery_id,
                    "error_category": category.value,
                    "status": status.value,
                    "retry_count": new_retry,
                },
            )
            return ReplayResult(
                delivery=updated, evidence=None, reused=False, status=status
            )

        updated = delivery.model_copy(
            update={
                "status": DeliveryStatus.REPLAYED,
                "error_category": IngestionErrorCategory.NONE,
                "retry_count": delivery.retry_count + 1,
                "normalized_pr_key": envelope.normalized_pr_key,
            }
        )
        self._store.upsert_delivery(updated)
        self._obs.record_event(
            "ingestion.replayed",
            {
                "delivery_id": delivery_id,
                "normalized_pr_key": envelope.normalized_pr_key,
            },
        )
        return ReplayResult(
            delivery=updated,
            evidence=evidence,
            reused=False,
            status=DeliveryStatus.REPLAYED,
        )


__all__ = ["ReplayService", "ReplayResult"]
