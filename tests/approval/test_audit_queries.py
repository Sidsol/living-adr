"""Slice S010-05: append-only audit durability and SM-05 queries.

Proves the audit trail reconstructs, for any authoritative mutation, the full
who/what/when/which-node story by joining review, minting, validation-failure,
consumption, and mutation facts on ``decision_id`` (FR-10). Also proves the audit
store is durable across restarts and independent of feature 015's checkpoint
state (US-7, NFR-2).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from tests.approval._helpers import (
    FixedClock,
    SequentialIds,
    build_adr_record,
    build_command,
    build_context,
    build_repo,
)
from tests.fakes.in_memory_graph_store import InMemoryGraphStore

from living_adr.approval.audit_queries import (
    audit_timeline,
    build_decision_audit_trail,
    decision_mutation_links,
)
from living_adr.approval.minting import mint_approved_decision
from living_adr.approval.models import (
    AuditEventType,
    DecisionExpiredError,
)
from living_adr.approval.mutation_service import DurableApprovalBoundMutationService
from living_adr.approval.repository import (
    InMemoryApprovalAuditRepository,
    SqliteApprovalAuditRepository,
)
from living_adr.core.graph.approval_bound_mutation import upsert_fingerprint
from living_adr.workflow.state import ReviewAction


def _mint(audit, repo, clock):
    record = build_adr_record(repo, decision_id="placeholder")
    expected_fp = upsert_fingerprint(repo, record)
    result = mint_approved_decision(
        repo,
        build_command(ReviewAction.APPROVE),
        build_context(repo),
        target_fingerprint=expected_fp,
        audit=audit,
        clock=clock,
        id_provider=SequentialIds("mint"),
    )
    bound = build_adr_record(repo, decision_id=result.decision.decision_id)
    return result.decision, bound


def _mutate(audit, repo, clock):
    decision, record = _mint(audit, repo, clock)
    store = InMemoryGraphStore()
    service = DurableApprovalBoundMutationService(
        store, audit, clock=clock, id_provider=SequentialIds("audit")
    )
    result = service.authorize_and_upsert(repo, record, decision)
    return decision, result


# --- full SM-05 join for one decision ------------------------------------


def test_trail_joins_review_minting_consumption_and_mutation() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    decision, result = _mutate(audit, repo, FixedClock())

    trail = build_decision_audit_trail(audit, decision.decision_id)

    assert trail.was_minted is True
    assert trail.was_mutated is True
    assert trail.was_consumed is True
    assert trail.mutation_node_id == result.node_id.value
    assert trail.reviewer_id == "lead-1"
    assert trail.approved_content_hash == decision.adr_draft_content_hash
    assert trail.review_event is not None
    assert trail.review_event.decision_id == decision.decision_id
    # The taxonomy covers minting through mutation/consumption.
    assert AuditEventType.CAPABILITY_MINTED in trail.event_types
    assert AuditEventType.MUTATION_PERFORMED in trail.event_types
    assert AuditEventType.CONSUMPTION_RECORDED in trail.event_types
    assert trail.validation_failures == ()


def test_decision_mutation_links_resolve_to_graph_node() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    decision, result = _mutate(audit, repo, FixedClock())

    links = decision_mutation_links(audit)

    assert len(links) == 1
    link = links[0]
    assert link.decision_id == decision.decision_id
    assert link.node_id == result.node_id.value
    assert link.reviewer_id == "lead-1"
    assert link.repository_key == repo.key


# --- validation-failure auditing -----------------------------------------


def test_validation_failure_is_durably_audited() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    decision, record = _mint(audit, repo, FixedClock())

    # Validate well past the TTL: the mutation must fail closed and leave a
    # VALIDATION_FAILED audit row.
    late = FixedClock()
    late.advance(timedelta(minutes=20))
    store = InMemoryGraphStore()
    service = DurableApprovalBoundMutationService(
        store, audit, clock=late, id_provider=SequentialIds("audit")
    )
    with pytest.raises(DecisionExpiredError):
        service.authorize_and_upsert(repo, record, decision)

    assert store.write_calls == 0
    trail = build_decision_audit_trail(audit, decision.decision_id)
    assert trail.was_mutated is False
    assert trail.was_consumed is False
    assert len(trail.validation_failures) == 1
    assert (
        trail.validation_failures[0].failure_kind == "DecisionExpiredError"
    )


def test_audit_timeline_is_repository_scoped() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    other = build_repo("other-svc")
    _mutate(audit, repo, FixedClock())

    scoped = audit_timeline(audit, repository_key=repo.key)
    assert scoped, "expected audit events for the mutated repository"
    assert all(e.repository_key == repo.key for e in scoped)
    assert audit_timeline(audit, repository_key=other.key) == ()


# --- durability + separation from feature 015 checkpoints ----------------


def test_audit_durable_across_reopen_and_separate_from_checkpoints(
    tmp_path: Path,
) -> None:
    audit_db = tmp_path / "approval_audit.sqlite"
    # A stand-in for feature 015's LangGraph checkpoint store: a *separate*
    # SQLite file the approval audit must never depend on.
    checkpoint_db = tmp_path / "lg_checkpoints.sqlite"

    store = SqliteApprovalAuditRepository(audit_db)
    repo = build_repo()
    decision, result = _mutate(store, repo, FixedClock())
    store.close()

    # Wiping the (unrelated) checkpoint store must not affect approval audit.
    checkpoint_db.write_bytes(b"")
    assert audit_db.exists()
    assert audit_db != checkpoint_db

    reopened = SqliteApprovalAuditRepository(audit_db)
    trail = build_decision_audit_trail(reopened, decision.decision_id)
    assert trail.was_mutated is True
    assert trail.mutation_node_id == result.node_id.value
    assert AuditEventType.CAPABILITY_MINTED in trail.event_types
    assert reopened.find_review_event_for_decision(decision.decision_id) is not None
    reopened.close()
