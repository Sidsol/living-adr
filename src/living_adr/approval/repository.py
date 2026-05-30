"""Durable, append-only approval/audit repository (feature 010).

The repository is the workflow-service-owned write side for approval facts:
review events, minted-capability metadata, one-shot consumption, and the SM-05
audit trail. It is **separate from feature 015's LangGraph checkpoint tables** so
audit durability never depends on ephemeral workflow-state retention (US-7,
NFR-2).

Two interchangeable implementations sit behind :class:`ApprovalAuditRepository`:

* :class:`InMemoryApprovalAuditRepository` — the dependency-free test seam.
* :class:`SqliteApprovalAuditRepository` — durable persistence (SQLite WAL) per
  architecture #deployment (PoC same-host single-writer).

Append-only discipline: review events, consumptions, and audit events are
insert-only. Re-inserting an existing ``review_event_id`` / consuming an already
consumed ``decision_id`` for a different target is rejected rather than
overwriting history.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

from living_adr.approval.models import (
    ApprovalEvent,
    AuditEvent,
    AuditEventType,
    ConsumptionRecord,
    DecisionAlreadyConsumedError,
    MintedDecisionRecord,
)


@runtime_checkable
class ApprovalAuditRepository(Protocol):
    """Append-only persistence port for approval/audit facts."""

    # review events ---------------------------------------------------------
    def record_review_event(self, event: ApprovalEvent) -> ApprovalEvent: ...

    def get_review_event(self, review_event_id: str) -> ApprovalEvent | None: ...

    def list_review_events(
        self, repository_key: str | None = None
    ) -> tuple[ApprovalEvent, ...]: ...

    # minted capabilities ---------------------------------------------------
    def record_minted_decision(
        self, record: MintedDecisionRecord
    ) -> MintedDecisionRecord: ...

    def get_minted_decision(
        self, decision_id: str
    ) -> MintedDecisionRecord | None: ...

    # one-shot consumption --------------------------------------------------
    def record_consumption(
        self, record: ConsumptionRecord
    ) -> ConsumptionRecord: ...

    def get_consumption(self, decision_id: str) -> ConsumptionRecord | None: ...

    # audit trail -----------------------------------------------------------
    def record_audit_event(self, event: AuditEvent) -> AuditEvent: ...

    def list_audit_events(
        self,
        decision_id: str | None = None,
        repository_key: str | None = None,
    ) -> tuple[AuditEvent, ...]: ...


class _ConsumptionConflict(DecisionAlreadyConsumedError):
    """A different fingerprint already consumed this decision (one-shot reuse)."""

    def __init__(self, decision_id: str) -> None:
        super().__init__(
            f"decision {decision_id!r} already consumed for a different "
            "mutation target"
        )


class InMemoryApprovalAuditRepository:
    """In-memory append-only approval/audit store for tests and PoC runs."""

    def __init__(self) -> None:
        self._review_events: dict[str, ApprovalEvent] = {}
        self._decisions: dict[str, MintedDecisionRecord] = {}
        self._consumptions: dict[str, ConsumptionRecord] = {}
        self._audit: list[AuditEvent] = []

    # review events ---------------------------------------------------------
    def record_review_event(self, event: ApprovalEvent) -> ApprovalEvent:
        if event.review_event_id in self._review_events:
            raise ValueError(
                f"review event {event.review_event_id!r} already recorded"
            )
        self._review_events[event.review_event_id] = event
        return event

    def get_review_event(self, review_event_id: str) -> ApprovalEvent | None:
        return self._review_events.get(review_event_id)

    def list_review_events(
        self, repository_key: str | None = None
    ) -> tuple[ApprovalEvent, ...]:
        events = self._review_events.values()
        if repository_key is not None:
            events = [e for e in events if e.repository.key == repository_key]
        return tuple(events)

    # minted capabilities ---------------------------------------------------
    def record_minted_decision(
        self, record: MintedDecisionRecord
    ) -> MintedDecisionRecord:
        if record.decision_id in self._decisions:
            raise ValueError(
                f"decision {record.decision_id!r} already minted"
            )
        self._decisions[record.decision_id] = record
        return record

    def get_minted_decision(
        self, decision_id: str
    ) -> MintedDecisionRecord | None:
        return self._decisions.get(decision_id)

    # one-shot consumption --------------------------------------------------
    def record_consumption(
        self, record: ConsumptionRecord
    ) -> ConsumptionRecord:
        existing = self._consumptions.get(record.decision_id)
        if existing is not None:
            if existing.target_fingerprint != record.target_fingerprint:
                raise _ConsumptionConflict(record.decision_id)
            return existing
        self._consumptions[record.decision_id] = record
        return record

    def get_consumption(self, decision_id: str) -> ConsumptionRecord | None:
        return self._consumptions.get(decision_id)

    # audit trail -----------------------------------------------------------
    def record_audit_event(self, event: AuditEvent) -> AuditEvent:
        self._audit.append(event)
        return event

    def list_audit_events(
        self,
        decision_id: str | None = None,
        repository_key: str | None = None,
    ) -> tuple[AuditEvent, ...]:
        events = self._audit
        if decision_id is not None:
            events = [e for e in events if e.decision_id == decision_id]
        if repository_key is not None:
            events = [e for e in events if e.repository_key == repository_key]
        return tuple(events)


class SqliteApprovalAuditRepository:
    """SQLite-backed (WAL) durable approval/audit store, append-only."""

    def __init__(self, db_path: Path | str) -> None:
        self._path = str(db_path)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_review_events (
                review_event_id TEXT PRIMARY KEY,
                event_json TEXT NOT NULL,
                repository_key TEXT NOT NULL,
                seq INTEGER
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_minted_decisions (
                decision_id TEXT PRIMARY KEY,
                record_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_consumptions (
                decision_id TEXT PRIMARY KEY,
                target_fingerprint TEXT NOT NULL,
                record_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_audit_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id TEXT NOT NULL,
                decision_id TEXT,
                repository_key TEXT NOT NULL,
                event_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # review events ---------------------------------------------------------
    def record_review_event(self, event: ApprovalEvent) -> ApprovalEvent:
        try:
            self._conn.execute(
                "INSERT INTO approval_review_events "
                "(review_event_id, event_json, repository_key) VALUES (?, ?, ?)",
                (
                    event.review_event_id,
                    event.model_dump_json(),
                    event.repository.key,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"review event {event.review_event_id!r} already recorded"
            ) from exc
        self._conn.commit()
        return event

    def get_review_event(self, review_event_id: str) -> ApprovalEvent | None:
        cur = self._conn.execute(
            "SELECT event_json FROM approval_review_events "
            "WHERE review_event_id = ?",
            (review_event_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return ApprovalEvent.model_validate_json(row["event_json"])

    def list_review_events(
        self, repository_key: str | None = None
    ) -> tuple[ApprovalEvent, ...]:
        if repository_key is None:
            cur = self._conn.execute(
                "SELECT event_json FROM approval_review_events ORDER BY rowid"
            )
        else:
            cur = self._conn.execute(
                "SELECT event_json FROM approval_review_events "
                "WHERE repository_key = ? ORDER BY rowid",
                (repository_key,),
            )
        return tuple(
            ApprovalEvent.model_validate_json(row["event_json"])
            for row in cur.fetchall()
        )

    # minted capabilities ---------------------------------------------------
    def record_minted_decision(
        self, record: MintedDecisionRecord
    ) -> MintedDecisionRecord:
        try:
            self._conn.execute(
                "INSERT INTO approval_minted_decisions "
                "(decision_id, record_json) VALUES (?, ?)",
                (record.decision_id, record.model_dump_json()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"decision {record.decision_id!r} already minted"
            ) from exc
        self._conn.commit()
        return record

    def get_minted_decision(
        self, decision_id: str
    ) -> MintedDecisionRecord | None:
        cur = self._conn.execute(
            "SELECT record_json FROM approval_minted_decisions "
            "WHERE decision_id = ?",
            (decision_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return MintedDecisionRecord.model_validate_json(row["record_json"])

    # one-shot consumption --------------------------------------------------
    def record_consumption(
        self, record: ConsumptionRecord
    ) -> ConsumptionRecord:
        existing = self.get_consumption(record.decision_id)
        if existing is not None:
            if existing.target_fingerprint != record.target_fingerprint:
                raise _ConsumptionConflict(record.decision_id)
            return existing
        try:
            self._conn.execute(
                "INSERT INTO approval_consumptions "
                "(decision_id, target_fingerprint, record_json) VALUES (?, ?, ?)",
                (
                    record.decision_id,
                    record.target_fingerprint,
                    record.model_dump_json(),
                ),
            )
        except sqlite3.IntegrityError:
            # Raced insert: re-read and reconcile against the durable row.
            self._conn.rollback()
            current = self.get_consumption(record.decision_id)
            if current is None:
                raise
            if current.target_fingerprint != record.target_fingerprint:
                raise _ConsumptionConflict(record.decision_id) from None
            return current
        self._conn.commit()
        return record

    def get_consumption(self, decision_id: str) -> ConsumptionRecord | None:
        cur = self._conn.execute(
            "SELECT record_json FROM approval_consumptions WHERE decision_id = ?",
            (decision_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return ConsumptionRecord.model_validate_json(row["record_json"])

    # audit trail -----------------------------------------------------------
    def record_audit_event(self, event: AuditEvent) -> AuditEvent:
        self._conn.execute(
            "INSERT INTO approval_audit_events "
            "(audit_id, decision_id, repository_key, event_json) "
            "VALUES (?, ?, ?, ?)",
            (
                event.audit_id,
                event.decision_id,
                event.repository_key,
                event.model_dump_json(),
            ),
        )
        self._conn.commit()
        return event

    def list_audit_events(
        self,
        decision_id: str | None = None,
        repository_key: str | None = None,
    ) -> tuple[AuditEvent, ...]:
        clauses: list[str] = []
        params: list[object] = []
        if decision_id is not None:
            clauses.append("decision_id = ?")
            params.append(decision_id)
        if repository_key is not None:
            clauses.append("repository_key = ?")
            params.append(repository_key)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        cur = self._conn.execute(
            f"SELECT event_json FROM approval_audit_events{where} ORDER BY seq",
            tuple(params),
        )
        return tuple(
            AuditEvent.model_validate_json(row["event_json"])
            for row in cur.fetchall()
        )


def audit_event_types(
    events: tuple[AuditEvent, ...],
) -> tuple[AuditEventType, ...]:
    """Convenience: project the ordered event-type sequence from an audit slice."""

    return tuple(e.event_type for e in events)


__all__ = [
    "ApprovalAuditRepository",
    "InMemoryApprovalAuditRepository",
    "SqliteApprovalAuditRepository",
    "audit_event_types",
]
