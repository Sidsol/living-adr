"""Durable approval-bound mutation orchestration (feature 010).

Feature 006 introduced :class:`ApprovalBoundMutationService` as the *only* code
path allowed to call :class:`ArchitectureGraphStore` write methods, but its
one-shot tracking was in-process and it had no TTL or durable audit. Feature 010
implements that deferred durability here: every authoritative write is validated
just-in-time, consumed exactly once against a durable consumption record, and
evidenced in the append-only audit trail.

:class:`DurableApprovalBoundMutationService` wraps the feature 006 service so the
graph adapter is still reached only through that single boundary (adapter
neutrality preserved), while adding:

* one-shot durable consumption keyed by ``decision_id`` (replay rejected),
* idempotent retry for the *same* decision + same target fingerprint (returns the
  prior result without a second write),
* ``DecisionAlreadyConsumedError`` when a consumed decision is re-presented for a
  different target,
* fail-closed TTL / content / scope validation with audit on every rejection.

It satisfies the workflow's ``GraphMutationService`` seam (``upsert_adr_node``) so
feature 015's mutation handoff can call it directly.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from living_adr.approval.models import (
    DEFAULT_DECISION_TTL,
    ApprovedReviewDecision,
    AuditDurabilityError,
    AuditEvent,
    AuditEventType,
    ConsumptionRecord,
    DecisionAlreadyConsumedError,
)
from living_adr.approval.repository import ApprovalAuditRepository
from living_adr.approval.validation import validate_for_mutation
from living_adr.core.adr import ADRRecord
from living_adr.core.graph.approval_bound_mutation import (
    ApprovalBoundMutationService,
    upsert_fingerprint,
)
from living_adr.core.graph.models import NodeId
from living_adr.core.graph.ports import ArchitectureGraphStore
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.repository import RepositoryIdentity

Clock = Callable[[], datetime]
IdProvider = Callable[[], str]


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _default_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class AuthorizedMutationResult:
    """Outcome of one authorised, audited graph mutation."""

    decision_id: str
    node_id: NodeId
    idempotent_replay: bool


@runtime_checkable
class AuthoritativeMutationService(Protocol):
    """The single authoritative-mutation boundary feature 010 owns (FR-9).

    Any code that wants to change authoritative graph context must call a service
    satisfying this Protocol; the concrete adapter is reached only through it, so
    workflow and MCP callers cannot bypass approval validation. It is deliberately
    narrow — it exposes *authorised* writes only, never raw store handles.
    """

    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision | None,
    ) -> NodeId: ...

    def authorize_and_upsert(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision | None,
    ) -> AuthorizedMutationResult: ...


class DurableApprovalBoundMutationService:
    """Approval-bound graph writes with durable one-shot consumption + audit."""

    def __init__(
        self,
        store: ArchitectureGraphStore,
        audit: ApprovalAuditRepository,
        *,
        observability: Observability | None = None,
        clock: Clock = _default_clock,
        ttl: timedelta = DEFAULT_DECISION_TTL,
        id_provider: IdProvider = _default_id,
    ) -> None:
        self._obs = observability or NoOpObservability()
        # The feature 006 service remains the sole code path to the store.
        self._core = ApprovalBoundMutationService(store, self._obs)
        self._audit = audit
        self._clock = clock
        self._ttl = ttl
        self._ids = id_provider

    # ------------------------------------------------------------------ upsert
    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision | None,
    ) -> NodeId:
        """``GraphMutationService`` seam — returns the upserted node id."""

        return self.authorize_and_upsert(repository, adr, decision).node_id

    def authorize_and_upsert(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision | None,
    ) -> AuthorizedMutationResult:
        expected_fp = upsert_fingerprint(repository, adr)

        # 1. One-shot / idempotency gate BEFORE binding checks so a consumed
        #    decision re-presented for a different target is reported as reuse,
        #    not a fresh target mismatch (US-4).
        if decision is not None and decision.approved:
            prior = self._audit.get_consumption(decision.decision_id)
            if prior is not None:
                if prior.target_fingerprint == expected_fp:
                    self._emit_replay(repository, decision, prior)
                    return AuthorizedMutationResult(
                        decision_id=decision.decision_id,
                        node_id=NodeId(
                            repository=repository, value=prior.node_id or ""
                        ),
                        idempotent_replay=True,
                    )
                raise DecisionAlreadyConsumedError(
                    "this approved decision has already been consumed for a "
                    "different mutation target"
                )

        # 2. Fail-closed validation (records VALIDATION_FAILED audit on failure).
        minted = (
            self._audit.get_minted_decision(decision.decision_id)
            if decision is not None
            else None
        )
        dec = validate_for_mutation(
            decision,
            repository=repository,
            expected_fingerprint=expected_fp,
            audit=self._audit,
            current_content=adr.markdown or None,
            clock=self._clock,
            ttl=self._ttl,
            minted_record=minted,
            id_provider=self._ids,
        )

        # 3. Perform the authoritative write through the feature 006 boundary.
        node = self._core.upsert_adr_node(repository, adr, dec)

        # 4. Record consumption atomically with the mutation result + audit.
        consumed_at = self._clock()
        consumption = ConsumptionRecord(
            decision_id=dec.decision_id,
            target_fingerprint=expected_fp,
            repository_key=repository.key,
            outcome="mutated",
            node_id=node.value,
            detail="upsert_adr_node",
            consumed_at=consumed_at,
        )
        try:
            stored = self._audit.record_consumption(consumption)
        except DecisionAlreadyConsumedError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed on audit failure
            raise AuditDurabilityError(
                "consumption persistence failed after mutation"
            ) from exc

        if stored is not consumption and stored.node_id:
            # A concurrent identical commit won the race: treat as idempotent.
            node = NodeId(repository=repository, value=stored.node_id)
            self._emit_replay(repository, dec, stored)
            return AuthorizedMutationResult(
                decision_id=dec.decision_id,
                node_id=node,
                idempotent_replay=True,
            )

        self._record_audit(
            AuditEventType.MUTATION_PERFORMED,
            repository_key=repository.key,
            recorded_at=consumed_at,
            decision_id=dec.decision_id,
            reviewer_id=dec.reviewer_id,
            target_fingerprint=expected_fp,
            detail=f"node:{node.value}",
        )
        self._record_audit(
            AuditEventType.CONSUMPTION_RECORDED,
            repository_key=repository.key,
            recorded_at=consumed_at,
            decision_id=dec.decision_id,
            reviewer_id=dec.reviewer_id,
            target_fingerprint=expected_fp,
            detail="upsert_adr_node",
        )
        self._obs.record_event(
            "approval.mutation_consumed",
            {
                "repository": repository.key,
                "decision_id": dec.decision_id,
                "node_id": node.value,
            },
        )
        return AuthorizedMutationResult(
            decision_id=dec.decision_id,
            node_id=node,
            idempotent_replay=False,
        )

    # ----------------------------------------------------------------- helpers
    def _emit_replay(
        self,
        repository: RepositoryIdentity,
        decision: ApprovedReviewDecision,
        prior: ConsumptionRecord,
    ) -> None:
        self._obs.record_event(
            "approval.mutation_replayed",
            {
                "repository": repository.key,
                "decision_id": decision.decision_id,
                "node_id": prior.node_id,
            },
        )

    def _record_audit(
        self,
        event_type: AuditEventType,
        *,
        repository_key: str,
        recorded_at: datetime,
        decision_id: str | None,
        reviewer_id: str | None,
        target_fingerprint: str | None,
        detail: str,
    ) -> None:
        event = AuditEvent(
            audit_id=self._ids(),
            event_type=event_type,
            repository_key=repository_key,
            recorded_at=recorded_at,
            decision_id=decision_id,
            reviewer_id=reviewer_id,
            target_fingerprint=target_fingerprint,
            detail=detail,
        )
        try:
            self._audit.record_audit_event(event)
        except Exception as exc:  # noqa: BLE001 - fail closed
            raise AuditDurabilityError(
                "audit persistence failed during mutation"
            ) from exc


__all__ = [
    "DurableApprovalBoundMutationService",
    "AuthorizedMutationResult",
    "AuthoritativeMutationService",
]
