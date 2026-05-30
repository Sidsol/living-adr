"""Durable ingestion store: delivery idempotency + dead-letter state (feature 003).

Two interchangeable implementations behind :class:`IngestionStore`:

- :class:`InMemoryIngestionStore` — the primary, dependency-free test seam.
- :class:`SqliteIngestionStore` — durable persistence (SQLite WAL) per
  architecture #data-model, so idempotency/replay/dead-letter survive restarts.

The store holds **no secrets and no raw payloads**: only delivery metadata and
(from slice 4) immutable candidate evidence keyed by the normalized PR key.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from living_adr.core.ingestion import (
    DeliveryStatus,
    IngestionDelivery,
    IngestionErrorCategory,
)


@runtime_checkable
class IngestionStore(Protocol):
    """Provider-neutral persistence port for ingestion delivery state."""

    def get_delivery(self, delivery_id: str) -> IngestionDelivery | None: ...

    def upsert_delivery(self, delivery: IngestionDelivery) -> IngestionDelivery: ...

    def list_dead_letters(self) -> tuple[IngestionDelivery, ...]: ...


class InMemoryIngestionStore:
    """In-memory delivery store for tests and single-process PoC runs."""

    def __init__(self) -> None:
        self._deliveries: dict[str, IngestionDelivery] = {}

    def get_delivery(self, delivery_id: str) -> IngestionDelivery | None:
        return self._deliveries.get(delivery_id)

    def upsert_delivery(self, delivery: IngestionDelivery) -> IngestionDelivery:
        self._deliveries[delivery.delivery_id] = delivery
        return delivery

    def list_dead_letters(self) -> tuple[IngestionDelivery, ...]:
        return tuple(
            d
            for d in self._deliveries.values()
            if d.status is DeliveryStatus.DEAD_LETTER
        )


_DELIVERY_COLUMNS = (
    "delivery_id",
    "provider",
    "status",
    "error_category",
    "repository_key",
    "normalized_pr_key",
    "pr_number",
    "retry_count",
    "received_at",
    "detail",
)


class SqliteIngestionStore:
    """SQLite-backed delivery store (WAL) for durable idempotency/replay."""

    def __init__(self, db_path: Path | str) -> None:
        self._path = str(db_path)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_deliveries (
                delivery_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                error_category TEXT NOT NULL,
                repository_key TEXT,
                normalized_pr_key TEXT,
                pr_number INTEGER,
                retry_count INTEGER NOT NULL,
                received_at TEXT NOT NULL,
                detail TEXT
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _to_row(delivery: IngestionDelivery) -> tuple[object, ...]:
        return (
            delivery.delivery_id,
            delivery.provider,
            delivery.status.value,
            delivery.error_category.value,
            delivery.repository_key,
            delivery.normalized_pr_key,
            delivery.pr_number,
            delivery.retry_count,
            delivery.received_at.isoformat(),
            delivery.detail,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> IngestionDelivery:
        return IngestionDelivery(
            delivery_id=row["delivery_id"],
            provider=row["provider"],
            status=DeliveryStatus(row["status"]),
            error_category=IngestionErrorCategory(row["error_category"]),
            repository_key=row["repository_key"],
            normalized_pr_key=row["normalized_pr_key"],
            pr_number=row["pr_number"],
            retry_count=row["retry_count"],
            received_at=datetime.fromisoformat(row["received_at"]),
            detail=row["detail"],
        )

    def get_delivery(self, delivery_id: str) -> IngestionDelivery | None:
        cur = self._conn.execute(
            "SELECT * FROM ingestion_deliveries WHERE delivery_id = ?",
            (delivery_id,),
        )
        row = cur.fetchone()
        return self._from_row(row) if row is not None else None

    def upsert_delivery(self, delivery: IngestionDelivery) -> IngestionDelivery:
        placeholders = ", ".join("?" for _ in _DELIVERY_COLUMNS)
        columns = ", ".join(_DELIVERY_COLUMNS)
        updates = ", ".join(
            f"{col}=excluded.{col}"
            for col in _DELIVERY_COLUMNS
            if col != "delivery_id"
        )
        self._conn.execute(
            f"INSERT INTO ingestion_deliveries ({columns}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(delivery_id) DO UPDATE SET {updates}",
            self._to_row(delivery),
        )
        self._conn.commit()
        return delivery

    def _all(self) -> Iterable[IngestionDelivery]:
        cur = self._conn.execute(
            "SELECT * FROM ingestion_deliveries ORDER BY received_at, delivery_id"
        )
        return (self._from_row(row) for row in cur.fetchall())

    def list_dead_letters(self) -> tuple[IngestionDelivery, ...]:
        return tuple(
            d for d in self._all() if d.status is DeliveryStatus.DEAD_LETTER
        )


__all__ = [
    "IngestionStore",
    "InMemoryIngestionStore",
    "SqliteIngestionStore",
]
