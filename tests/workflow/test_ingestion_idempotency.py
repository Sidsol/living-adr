"""Slice 2 RED tests: durable delivery idempotency store.

Covers first-insert, exact-duplicate prior-result return, skipped/rejected state
persistence, and dead-letter listing. Exercised against both the in-memory store
(primary test seam) and the SQLite-backed store (durability) so behavior is
identical across implementations.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from living_adr.core.ingestion import (
    DeliveryStatus,
    IngestionDelivery,
    IngestionErrorCategory,
)
from living_adr.persistence.ingestion_store import (
    InMemoryIngestionStore,
    SqliteIngestionStore,
)

RECEIVED_AT = datetime(2024, 6, 1, 9, 30, tzinfo=UTC)


def _delivery(
    delivery_id: str,
    status: DeliveryStatus = DeliveryStatus.ACCEPTED,
    **kwargs,
) -> IngestionDelivery:
    return IngestionDelivery(
        delivery_id=delivery_id,
        status=status,
        received_at=RECEIVED_AT,
        **kwargs,
    )


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryIngestionStore()
    return SqliteIngestionStore(tmp_path / "ingestion.db")


def test_unknown_delivery_returns_none(store) -> None:
    assert store.get_delivery("nope") is None


def test_first_insert_then_lookup_round_trips(store) -> None:
    delivery = _delivery(
        "d-1",
        repository_key="github.com/acme/widgets",
        normalized_pr_key="github:github.com/acme/widgets:42:abc",
        pr_number=42,
    )
    store.upsert_delivery(delivery)
    fetched = store.get_delivery("d-1")
    assert fetched is not None
    assert fetched.delivery_id == "d-1"
    assert fetched.status is DeliveryStatus.ACCEPTED
    assert fetched.repository_key == "github.com/acme/widgets"
    assert fetched.normalized_pr_key == "github:github.com/acme/widgets:42:abc"
    assert fetched.pr_number == 42


def test_duplicate_delivery_returns_prior_state(store) -> None:
    first = _delivery("d-2", status=DeliveryStatus.ACCEPTED, pr_number=7)
    store.upsert_delivery(first)
    # The handler would short-circuit on a found delivery; assert the stored
    # prior state is exactly what is returned and never silently mutated.
    prior = store.get_delivery("d-2")
    assert prior == first


def test_skipped_and_rejected_states_persist(store) -> None:
    skipped = _delivery(
        "d-skip",
        status=DeliveryStatus.SKIPPED,
        error_category=IngestionErrorCategory.NOT_MERGED,
    )
    rejected = _delivery(
        "d-reject",
        status=DeliveryStatus.REJECTED,
        error_category=IngestionErrorCategory.UNCONFIGURED_REPOSITORY,
    )
    store.upsert_delivery(skipped)
    store.upsert_delivery(rejected)
    assert store.get_delivery("d-skip").error_category is (
        IngestionErrorCategory.NOT_MERGED
    )
    assert store.get_delivery("d-reject").status is DeliveryStatus.REJECTED


def test_dead_letter_listing(store) -> None:
    store.upsert_delivery(_delivery("ok", status=DeliveryStatus.ACCEPTED))
    store.upsert_delivery(
        _delivery(
            "dead",
            status=DeliveryStatus.DEAD_LETTER,
            error_category=IngestionErrorCategory.PERMISSION_DENIED,
        )
    )
    dead = store.list_dead_letters()
    assert [d.delivery_id for d in dead] == ["dead"]


def test_upsert_overwrites_in_place_for_replay_progress(store) -> None:
    store.upsert_delivery(_delivery("d-3", status=DeliveryStatus.RETRYABLE))
    updated = _delivery("d-3", status=DeliveryStatus.ACCEPTED, retry_count=1)
    store.upsert_delivery(updated)
    fetched = store.get_delivery("d-3")
    assert fetched.status is DeliveryStatus.ACCEPTED
    assert fetched.retry_count == 1
