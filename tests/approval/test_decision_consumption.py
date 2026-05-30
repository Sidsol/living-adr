"""Slice S010-04: one-shot consumption and idempotent retry.

Proves a capability authorises exactly one mutation: a successful upsert consumes
it durably, an identical retry returns the prior result without a second graph
write, and re-presenting the decision for a different target raises
``DecisionAlreadyConsumedError``. Consumption survives a SQLite reopen.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from tests.approval._helpers import (
    DRAFT_HASH,
    DRAFT_MARKDOWN,
    FixedClock,
    SequentialIds,
    build_adr_record,
    build_command,
    build_context,
    build_repo,
)
from tests.fakes.in_memory_graph_store import InMemoryGraphStore

from living_adr.approval.minting import mint_approved_decision
from living_adr.approval.models import (
    ConsumptionRecord,
    DecisionAlreadyConsumedError,
)
from living_adr.approval.mutation_service import DurableApprovalBoundMutationService
from living_adr.approval.repository import (
    InMemoryApprovalAuditRepository,
    SqliteApprovalAuditRepository,
)
from living_adr.core.graph.approval_bound_mutation import upsert_fingerprint
from living_adr.workflow.state import ReviewAction


def _mint_for(audit, repo, store):
    """Mint a capability whose target fingerprint matches the upsert record."""

    # Build the record first so we can bind the decision to its exact fingerprint.
    # decision_id is the 2nd id from the provider; bind fingerprint accordingly.
    ctx = build_context(repo)
    # Pre-compute the record/fingerprint using a placeholder decision id, then
    # mint with that fingerprint.
    placeholder = build_adr_record(repo, decision_id="decision-x")
    expected_fp = upsert_fingerprint(repo, placeholder)
    result = mint_approved_decision(
        repo,
        build_command(ReviewAction.APPROVE),
        ctx,
        target_fingerprint=expected_fp,
        audit=audit,
        clock=FixedClock(),
        id_provider=SequentialIds("id"),
    )
    record = build_adr_record(repo, decision_id=result.decision.decision_id)
    return result.decision, record


# --- consumption record model ---------------------------------------------


def test_consumption_record_requires_keys() -> None:
    rec = ConsumptionRecord(
        decision_id="d-1",
        target_fingerprint="fp-1",
        repository_key="github.com/acme/living-adr",
        outcome="mutated",
        node_id="node:adr-1",
        consumed_at=datetime(2026, 1, 1),
    )
    assert rec.decision_id == "d-1"
    with pytest.raises(ValueError):
        ConsumptionRecord(
            decision_id="  ",
            target_fingerprint="fp-1",
            repository_key="k",
            outcome="mutated",
            consumed_at=datetime(2026, 1, 1),
        )


# --- atomic consumption at the repository --------------------------------


def test_repository_consumption_is_one_shot_and_idempotent() -> None:
    audit = InMemoryApprovalAuditRepository()
    rec = ConsumptionRecord(
        decision_id="d-1",
        target_fingerprint="fp-1",
        repository_key="k",
        outcome="mutated",
        node_id="node:1",
        consumed_at=datetime(2026, 1, 1),
    )
    audit.record_consumption(rec)
    # Same fingerprint returns the prior record (idempotent).
    again = audit.record_consumption(
        ConsumptionRecord(
            decision_id="d-1",
            target_fingerprint="fp-1",
            repository_key="k",
            outcome="mutated",
            node_id="node:1",
            consumed_at=datetime(2026, 1, 2),
        )
    )
    assert again.consumed_at == rec.consumed_at
    # Different fingerprint for the same decision is rejected reuse.
    with pytest.raises(DecisionAlreadyConsumedError):
        audit.record_consumption(
            ConsumptionRecord(
                decision_id="d-1",
                target_fingerprint="fp-2",
                repository_key="k",
                outcome="mutated",
                consumed_at=datetime(2026, 1, 2),
            )
        )


def test_sqlite_consumption_survives_reopen(tmp_path: Path) -> None:
    db = tmp_path / "consume.sqlite"
    store = SqliteApprovalAuditRepository(db)
    store.record_consumption(
        ConsumptionRecord(
            decision_id="d-9",
            target_fingerprint="fp-9",
            repository_key="k",
            outcome="mutated",
            node_id="node:9",
            consumed_at=datetime(2026, 1, 1),
        )
    )
    store.close()
    reopened = SqliteApprovalAuditRepository(db)
    got = reopened.get_consumption("d-9")
    assert got is not None
    assert got.node_id == "node:9"
    # Replay rejection persists across restart.
    with pytest.raises(DecisionAlreadyConsumedError):
        reopened.record_consumption(
            ConsumptionRecord(
                decision_id="d-9",
                target_fingerprint="fp-other",
                repository_key="k",
                outcome="mutated",
                consumed_at=datetime(2026, 1, 2),
            )
        )
    reopened.close()


# --- service-level one-shot + idempotent retry ---------------------------


def test_first_upsert_consumes_then_retry_is_idempotent() -> None:
    audit = InMemoryApprovalAuditRepository()
    store = InMemoryGraphStore()
    repo = build_repo()
    decision, record = _mint_for(audit, repo, store)
    service = DurableApprovalBoundMutationService(
        store, audit, clock=FixedClock(), id_provider=SequentialIds("audit")
    )

    first = service.authorize_and_upsert(repo, record, decision)
    assert first.idempotent_replay is False
    assert store.write_calls == 1
    assert audit.get_consumption(decision.decision_id) is not None

    # Identical retry after a successful commit returns the prior result and
    # performs no second mutation (US-4).
    second = service.authorize_and_upsert(repo, record, decision)
    assert second.idempotent_replay is True
    assert second.node_id == first.node_id
    assert store.write_calls == 1


def test_reuse_for_different_target_is_rejected() -> None:
    audit = InMemoryApprovalAuditRepository()
    store = InMemoryGraphStore()
    repo = build_repo()
    decision, record = _mint_for(audit, repo, store)
    service = DurableApprovalBoundMutationService(
        store, audit, clock=FixedClock(), id_provider=SequentialIds("audit")
    )
    service.authorize_and_upsert(repo, record, decision)

    # A different record (different content hash + id) yields a different
    # fingerprint; the consumed decision must be rejected as reuse.
    other_record = build_adr_record(
        repo,
        decision_id=decision.decision_id,
        adr_id="adr-2",
        content_hash=DRAFT_HASH,
        markdown=DRAFT_MARKDOWN,
    )
    with pytest.raises(DecisionAlreadyConsumedError):
        service.authorize_and_upsert(repo, other_record, decision)
    assert store.write_calls == 1
