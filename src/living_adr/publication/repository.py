"""Durable publication record repository + intent reservation (feature 011).

The publication record is the primary idempotency store for publish-back (FR-8,
FR-9): it is reserved (intent) before the remote GitHub write and finalised with
the commit outcome afterwards. It is keyed by ``decision_id`` so a webhook replay
or workflow retry of the same approved decision cannot create a duplicate ADR
file (US-4). A same-``decision_id`` reservation with a *different* fingerprint is
rejected as a target mismatch rather than overwriting history.

Two interchangeable implementations sit behind
:class:`PublicationRecordRepository`, mirroring feature 010's approval store:

* :class:`InMemoryPublicationRepository` — dependency-free test seam.
* :class:`SqlitePublicationRepository` — durable persistence (SQLite WAL).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

from living_adr.publication.models import (
    PublicationRecord,
    PublicationTargetMismatchError,
)


@runtime_checkable
class PublicationRecordRepository(Protocol):
    """Durable publication intent/result store keyed by ``decision_id``."""

    def reserve(self, record: PublicationRecord) -> PublicationRecord: ...

    def finalize(self, record: PublicationRecord) -> PublicationRecord: ...

    def get(self, decision_id: str) -> PublicationRecord | None: ...

    def list(
        self, repository_key: str | None = None
    ) -> tuple[PublicationRecord, ...]: ...


def _reconcile(
    existing: PublicationRecord, incoming: PublicationRecord
) -> PublicationRecord:
    if existing.fingerprint != incoming.fingerprint:
        raise PublicationTargetMismatchError(
            f"decision {incoming.decision_id!r} already reserved for a different "
            "publication target (fingerprint mismatch)"
        )
    return existing


class InMemoryPublicationRepository:
    """In-memory publication record store for tests and PoC runs."""

    def __init__(self) -> None:
        self._by_decision: dict[str, PublicationRecord] = {}

    def reserve(self, record: PublicationRecord) -> PublicationRecord:
        existing = self._by_decision.get(record.decision_id)
        if existing is not None:
            return _reconcile(existing, record)
        self._by_decision[record.decision_id] = record
        return record

    def finalize(self, record: PublicationRecord) -> PublicationRecord:
        existing = self._by_decision.get(record.decision_id)
        if existing is not None:
            _reconcile(existing, record)
        self._by_decision[record.decision_id] = record
        return record

    def get(self, decision_id: str) -> PublicationRecord | None:
        return self._by_decision.get(decision_id)

    def list(
        self, repository_key: str | None = None
    ) -> tuple[PublicationRecord, ...]:
        records = self._by_decision.values()
        if repository_key is not None:
            records = [r for r in records if r.repository_key == repository_key]
        return tuple(records)


class SqlitePublicationRepository:
    """SQLite-backed (WAL) durable publication record store."""

    def __init__(self, db_path: Path | str) -> None:
        self._path = str(db_path)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS publication_records (
                decision_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                repository_key TEXT NOT NULL,
                record_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def reserve(self, record: PublicationRecord) -> PublicationRecord:
        existing = self.get(record.decision_id)
        if existing is not None:
            return _reconcile(existing, record)
        try:
            self._conn.execute(
                "INSERT INTO publication_records "
                "(decision_id, fingerprint, repository_key, record_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    record.decision_id,
                    record.fingerprint,
                    record.repository_key,
                    record.model_dump_json(),
                ),
            )
        except sqlite3.IntegrityError:
            self._conn.rollback()
            current = self.get(record.decision_id)
            if current is None:
                raise
            return _reconcile(current, record)
        self._conn.commit()
        return record

    def finalize(self, record: PublicationRecord) -> PublicationRecord:
        existing = self.get(record.decision_id)
        if existing is not None:
            _reconcile(existing, record)
        self._conn.execute(
            "INSERT INTO publication_records "
            "(decision_id, fingerprint, repository_key, record_json) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(decision_id) DO UPDATE SET "
            "fingerprint=excluded.fingerprint, "
            "repository_key=excluded.repository_key, "
            "record_json=excluded.record_json",
            (
                record.decision_id,
                record.fingerprint,
                record.repository_key,
                record.model_dump_json(),
            ),
        )
        self._conn.commit()
        return record

    def get(self, decision_id: str) -> PublicationRecord | None:
        cur = self._conn.execute(
            "SELECT record_json FROM publication_records WHERE decision_id = ?",
            (decision_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return PublicationRecord.model_validate_json(row["record_json"])

    def list(
        self, repository_key: str | None = None
    ) -> tuple[PublicationRecord, ...]:
        if repository_key is None:
            cur = self._conn.execute(
                "SELECT record_json FROM publication_records ORDER BY rowid"
            )
        else:
            cur = self._conn.execute(
                "SELECT record_json FROM publication_records "
                "WHERE repository_key = ? ORDER BY rowid",
                (repository_key,),
            )
        return tuple(
            PublicationRecord.model_validate_json(row["record_json"])
            for row in cur.fetchall()
        )


__all__ = [
    "PublicationRecordRepository",
    "InMemoryPublicationRepository",
    "SqlitePublicationRepository",
]
