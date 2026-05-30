"""Operator-facing replay entry point for the workflow service (slice 5).

A thin callable wrapper around :class:`~living_adr.workflow.replay.ReplayService`
so an operator (or a future CLI/admin route) can reprocess a stored delivery by
id without bypassing idempotency or origin-audit guarantees. It only ever acts on
deliveries already persisted by the verified webhook path — never on unverified
external input.
"""

from __future__ import annotations

from living_adr.core.observability import Observability
from living_adr.core.scm import SCMProvider
from living_adr.persistence.ingestion_store import IngestionStore
from living_adr.workflow.replay import ReplayResult, ReplayService


def replay_delivery(
    delivery_id: str,
    store: IngestionStore,
    provider: SCMProvider,
    observability: Observability | None = None,
) -> ReplayResult:
    """Replay a single stored delivery by id and return the outcome."""

    service = ReplayService(
        store=store, provider=provider, observability=observability
    )
    return service.replay_delivery(delivery_id)


class OperatorReplay:
    """Reusable operator handle bound to a store + provider for repeated replays."""

    def __init__(
        self,
        store: IngestionStore,
        provider: SCMProvider,
        observability: Observability | None = None,
    ) -> None:
        self._service = ReplayService(
            store=store, provider=provider, observability=observability
        )

    def __call__(self, delivery_id: str) -> ReplayResult:
        return self._service.replay_delivery(delivery_id)


__all__ = ["replay_delivery", "OperatorReplay"]
