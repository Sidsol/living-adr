"""Ingestion delivery state, outcomes, and error categories (feature 003).

Provider-neutral state for a single webhook delivery, keyed by the provider
delivery id (the primary idempotency key, architecture #cross-cutting, NFR-2).
PR numbers alone are never used as idempotency keys (they collide across
repositories); the repository-scoped normalized PR key and the delivery id are.

State is modelled as an immutable :class:`IngestionDelivery` plus pure transition
helpers that return updated copies, so persistence layers can store deterministic
snapshots and replay/dead-letter recovery can reason about retry counts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DeliveryStatus(StrEnum):
    """Terminal/intermediate processing state of a webhook delivery."""

    RECEIVED = "received"
    ACCEPTED = "accepted"
    SKIPPED = "skipped"
    REJECTED = "rejected"
    FAILED = "failed"
    RETRYABLE = "retryable"
    DEAD_LETTER = "dead_letter"
    REPLAYED = "replayed"


class IngestionErrorCategory(StrEnum):
    """Why a delivery was skipped, rejected, failed, or dead-lettered."""

    NONE = "none"
    INVALID_SIGNATURE = "invalid_signature"
    MISSING_HEADERS = "missing_headers"
    UNCONFIGURED_REPOSITORY = "unconfigured_repository"
    NOT_PULL_REQUEST = "not_pull_request"
    NOT_MERGED = "not_merged"
    MALFORMED_PAYLOAD = "malformed_payload"
    RATE_LIMITED = "rate_limited"
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_NOT_FOUND = "resource_not_found"
    TRANSIENT = "transient"
    UNKNOWN = "unknown"


# Categories that justify a retry/replay rather than a permanent dead-letter.
RETRYABLE_CATEGORIES: frozenset[IngestionErrorCategory] = frozenset(
    {IngestionErrorCategory.RATE_LIMITED, IngestionErrorCategory.TRANSIENT}
)


def _now() -> datetime:
    return datetime.now(UTC)


class IngestionDelivery(BaseModel):
    """Immutable processing record for one provider delivery id."""

    model_config = ConfigDict(frozen=True)

    delivery_id: str
    provider: str = "github"
    status: DeliveryStatus
    error_category: IngestionErrorCategory = IngestionErrorCategory.NONE
    repository_key: str | None = None
    normalized_pr_key: str | None = None
    pr_number: int | None = None
    retry_count: int = 0
    received_at: datetime = Field(default_factory=_now)
    detail: str | None = None

    def with_status(
        self,
        status: DeliveryStatus,
        *,
        error_category: IngestionErrorCategory | None = None,
        detail: str | None = None,
    ) -> IngestionDelivery:
        """Return a copy transitioned to ``status`` (pure, no mutation)."""

        update: dict[str, object] = {"status": status}
        if error_category is not None:
            update["error_category"] = error_category
        if detail is not None:
            update["detail"] = detail
        return self.model_copy(update=update)

    def incremented_retry(self) -> IngestionDelivery:
        """Return a copy with ``retry_count`` increased by one."""

        return self.model_copy(update={"retry_count": self.retry_count + 1})

    def to_dead_letter(self, *, detail: str | None = None) -> IngestionDelivery:
        """Transition to the terminal dead-letter state for operator triage."""

        update: dict[str, object] = {"status": DeliveryStatus.DEAD_LETTER}
        if detail is not None:
            update["detail"] = detail
        return self.model_copy(update=update)

    @property
    def is_retryable(self) -> bool:
        """True when the failure category warrants a retry/replay attempt."""

        return self.error_category in RETRYABLE_CATEGORIES


DEFAULT_MAX_RETRIES = 3


def classify_failure(
    category: IngestionErrorCategory,
    retry_count: int,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> DeliveryStatus:
    """Decide the next delivery status after a processing/fetch failure.

    - Retryable categories (rate limit, transient) stay ``RETRYABLE`` until the
      retry budget is exhausted, then become ``DEAD_LETTER``.
    - Non-retryable categories (permission, not-found, malformed, unknown) are
      poison and go straight to ``DEAD_LETTER`` for operator triage.
    """

    if category in RETRYABLE_CATEGORIES and retry_count < max_retries:
        return DeliveryStatus.RETRYABLE
    return DeliveryStatus.DEAD_LETTER


__all__ = [
    "DeliveryStatus",
    "IngestionErrorCategory",
    "RETRYABLE_CATEGORIES",
    "IngestionDelivery",
    "DEFAULT_MAX_RETRIES",
    "classify_failure",
]
