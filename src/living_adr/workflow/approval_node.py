"""Workflow approval-minting seam (feature 010 ↔ feature 015).

Feature 009 submits a capability-free :class:`ReviewResumeCommand`
(``approved_decision=None``) — minting authority belongs to feature 010. This
node is the bridge: given a paused-then-resumed workflow state, it records the
immutable review outcome and, for authorising actions, mints a one-shot
:class:`~living_adr.core.approval.ApprovedReviewDecision` bound to the exact
reviewed content hash and the *target fingerprint of the very ADR record the
mutation handoff will write*. The minted capability is attached to state so the
downstream :class:`StubMutationHandoffNode` performs an approval-bound,
durably-audited write.

The node imports no concrete graph adapter; it reuses the handoff's record
construction purely to compute the authorised target fingerprint, guaranteeing
the minted capability authorises exactly the mutation that will be attempted
(no fingerprint drift between mint and consume).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from living_adr.approval.minting import (
    MintResult,
    ReviewContext,
    mint_approved_decision,
    record_review_outcome,
)
from living_adr.approval.models import DEFAULT_DECISION_TTL
from living_adr.approval.repository import ApprovalAuditRepository
from living_adr.core.graph.approval_bound_mutation import upsert_fingerprint
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.workflow.nodes.protocols import StateUpdate
from living_adr.workflow.nodes.stubs import StubMutationHandoffNode
from living_adr.workflow.state import WorkflowState, derive_thread_id

Clock = Callable[[], datetime]
IdProvider = Callable[[], str]


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _default_id() -> str:
    return str(uuid.uuid4())


class ApprovalMintingNode:
    """Mint and attach a durable approval capability from a reviewer's command."""

    def __init__(
        self,
        audit: ApprovalAuditRepository,
        *,
        ttl: timedelta = DEFAULT_DECISION_TTL,
        clock: Clock = _default_clock,
        id_provider: IdProvider = _default_id,
        observability: Observability | None = None,
    ) -> None:
        self._audit = audit
        self._ttl = ttl
        self._clock = clock
        self._ids = id_provider
        self._obs = observability or NoOpObservability()
        # Reused only to construct the authoritative target record (no adapter).
        self._record_builder = StubMutationHandoffNode()

    def _context(self, state: WorkflowState) -> ReviewContext:
        if state.repository is None or state.draft is None:
            raise ValueError("approval minting requires repository scope and a draft")
        key = state.normalized_event_key or ""
        record = self._record_builder.build_adr_record(state)
        change_id = record.structural_change_id
        return ReviewContext(
            repository=state.repository,
            workflow_thread_id=derive_thread_id(state.repository, key),
            normalized_event_key=key,
            adr_draft_id=state.draft.draft_id,
            adr_draft_content_hash=state.draft.content_hash,
            structural_change_event_id=change_id,
            adr_record_id=record.adr_id,
        )

    def mint_for_state(self, state: WorkflowState) -> MintResult:
        """Record the review outcome and mint a capability for authorising actions."""

        command = state.resume_command
        if command is None:
            raise ValueError("approval minting requires a resume command")
        context = self._context(state)

        if not command.action.authorizes_mutation:
            event = record_review_outcome(
                state.repository,
                command,
                context,
                audit=self._audit,
                clock=self._clock,
                id_provider=self._ids,
                observability=self._obs,
            )
            return MintResult(event=event, decision=None, minted_record=None)

        # Bind the capability to the exact mutation target the handoff will write.
        record = self._record_builder.build_adr_record(state)
        target_fingerprint = upsert_fingerprint(state.repository, record)
        return mint_approved_decision(
            state.repository,
            command,
            context,
            target_fingerprint=target_fingerprint,
            audit=self._audit,
            ttl=self._ttl,
            clock=self._clock,
            id_provider=self._ids,
            observability=self._obs,
        )

    def __call__(self, state: WorkflowState) -> StateUpdate:
        result = self.mint_for_state(state)
        # Reject/defer mint no capability; leave approved_decision unset so the
        # handoff routes to its terminal no-mutation branch.
        return {"approved_decision": result.decision}


__all__ = [
    "ApprovalMintingNode",
]
