"""SM-05 audit queries over the durable approval trail (feature 010).

These read-side helpers assemble the append-only audit facts into the per-decision
and per-repository views SM-05 requires (FR-10): "for any authoritative mutation,
reconstruct who approved it, against which content, when it was consumed, and what
graph node it produced." Every fact is keyed by ``decision_id`` so the review,
minting, validation-failure, consumption, mutation, and publication steps join into
one ordered timeline.

The queries read only through :class:`ApprovalAuditRepository`, so they work
identically against the in-memory test seam and the SQLite durable store, and they
never depend on feature 015's LangGraph checkpoint state (audit durability is
independent of ephemeral workflow-state retention — US-7, NFR-2).
"""

from __future__ import annotations

from dataclasses import dataclass

from living_adr.approval.models import (
    ApprovalEvent,
    AuditEvent,
    AuditEventType,
    ConsumptionRecord,
    MintedDecisionRecord,
)
from living_adr.approval.repository import ApprovalAuditRepository


@dataclass(frozen=True)
class DecisionAuditTrail:
    """The complete SM-05 join for one ``decision_id``.

    Fields are ``None`` when the corresponding step never happened (e.g. a
    rejected outcome has no minted capability; a decision validated but never
    mutated has no consumption).
    """

    decision_id: str
    review_event: ApprovalEvent | None
    minted: MintedDecisionRecord | None
    consumption: ConsumptionRecord | None
    audit_events: tuple[AuditEvent, ...]

    @property
    def event_types(self) -> tuple[AuditEventType, ...]:
        """The ordered audit-event-type sequence for this decision."""

        return tuple(e.event_type for e in self.audit_events)

    @property
    def was_minted(self) -> bool:
        return self.minted is not None

    @property
    def was_mutated(self) -> bool:
        return any(
            e.event_type is AuditEventType.MUTATION_PERFORMED
            for e in self.audit_events
        )

    @property
    def was_consumed(self) -> bool:
        return self.consumption is not None

    @property
    def mutation_node_id(self) -> str | None:
        """The graph node this decision authorised, if it was consumed."""

        return self.consumption.node_id if self.consumption is not None else None

    @property
    def validation_failures(self) -> tuple[AuditEvent, ...]:
        return tuple(
            e
            for e in self.audit_events
            if e.event_type is AuditEventType.VALIDATION_FAILED
        )

    @property
    def reviewer_id(self) -> str | None:
        if self.review_event is not None:
            return self.review_event.reviewer_id
        if self.minted is not None:
            return self.minted.reviewer_id
        return None

    @property
    def approved_content_hash(self) -> str | None:
        if self.review_event is not None:
            return self.review_event.adr_draft_content_hash
        if self.minted is not None:
            return self.minted.adr_draft_content_hash
        return None


@dataclass(frozen=True)
class DecisionMutationLink:
    """A resolved decision → graph-node mutation edge (SM-05 traceability)."""

    decision_id: str
    repository_key: str
    node_id: str | None
    reviewer_id: str | None


def build_decision_audit_trail(
    audit: ApprovalAuditRepository, decision_id: str
) -> DecisionAuditTrail:
    """Join every durable approval fact for ``decision_id`` into one trail."""

    return DecisionAuditTrail(
        decision_id=decision_id,
        review_event=audit.find_review_event_for_decision(decision_id),
        minted=audit.get_minted_decision(decision_id),
        consumption=audit.get_consumption(decision_id),
        audit_events=audit.list_audit_events(decision_id=decision_id),
    )


def decision_mutation_links(
    audit: ApprovalAuditRepository, repository_key: str | None = None
) -> tuple[DecisionMutationLink, ...]:
    """Resolve every consumed decision to the graph node it authorised."""

    links: list[DecisionMutationLink] = []
    for consumption in audit.list_consumptions(repository_key):
        minted = audit.get_minted_decision(consumption.decision_id)
        links.append(
            DecisionMutationLink(
                decision_id=consumption.decision_id,
                repository_key=consumption.repository_key,
                node_id=consumption.node_id,
                reviewer_id=minted.reviewer_id if minted is not None else None,
            )
        )
    return tuple(links)


def audit_timeline(
    audit: ApprovalAuditRepository, repository_key: str | None = None
) -> tuple[AuditEvent, ...]:
    """The ordered append-only audit timeline (optionally scoped to a repo)."""

    return audit.list_audit_events(repository_key=repository_key)


__all__ = [
    "DecisionAuditTrail",
    "DecisionMutationLink",
    "build_decision_audit_trail",
    "decision_mutation_links",
    "audit_timeline",
]
