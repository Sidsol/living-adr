"""ApprovalBoundMutationService — the only authoritative graph write path.

Workflow code never calls :class:`ArchitectureGraphStore` directly. It calls
this service, which validates an :class:`ApprovedReviewDecision` and only then
delegates exactly once to the underlying store. Every invalid approval (missing,
unapproved, wrong repository, drifted content, wrong target, or already
consumed) raises **before** any adapter call, so unapproved model output, MCP
requests, or workflow retries cannot mutate authoritative context
(architecture #service-boundaries; SM-05; FM-13).

The ``*_fingerprint`` helpers compute the stable target fingerprint for each
mutation. An ``ApprovedReviewDecision`` carries the fingerprint of the single
mutation it authorizes; a mismatch means the capability is being replayed
against a different target and is rejected.
"""

from __future__ import annotations

import hashlib

from living_adr.core.adr import ADRRecord
from living_adr.core.approval import (
    ApprovalRequiredError,
    ApprovedReviewDecision,
    DecisionAlreadyConsumedError,
    DecisionRepositoryMismatchError,
    DraftContentMismatchError,
    MutationFingerprintMismatchError,
)
from living_adr.core.graph.models import (
    GraphEdge,
    MigrationResult,
    NodeId,
    RelationshipType,
    SchemaVersion,
)
from living_adr.core.graph.ports import ArchitectureGraphStore
from living_adr.core.models import StructuralChange
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.repository import RepositoryIdentity


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def upsert_fingerprint(repository: RepositoryIdentity, adr: ADRRecord) -> str:
    return _fingerprint(
        "upsert_adr_node", repository.key, adr.adr_id, adr.content_hash
    )


def relationship_fingerprint(
    repository: RepositoryIdentity,
    from_node: NodeId,
    to_node: NodeId,
    relationship: RelationshipType,
) -> str:
    return _fingerprint(
        "add_relationship",
        repository.key,
        from_node.value,
        to_node.value,
        str(relationship),
    )


def structural_change_fingerprint(
    repository: RepositoryIdentity, change: StructuralChange, linked_adr: NodeId
) -> str:
    return _fingerprint(
        "record_structural_change",
        repository.key,
        change.change_id,
        linked_adr.value,
    )


def supersede_fingerprint(
    repository: RepositoryIdentity, prior_adr: NodeId, superseding_adr: NodeId
) -> str:
    return _fingerprint(
        "supersede_adr", repository.key, prior_adr.value, superseding_adr.value
    )


def retract_fingerprint(repository: RepositoryIdentity, adr: NodeId) -> str:
    return _fingerprint("retract_adr", repository.key, adr.value)


def migrate_fingerprint(
    repository: RepositoryIdentity, target_version: SchemaVersion
) -> str:
    return _fingerprint("migrate_schema", repository.key, target_version.label)


class ApprovalBoundMutationService:
    """Validates approval, then delegates exactly once to the graph store."""

    def __init__(
        self,
        store: ArchitectureGraphStore,
        observability: Observability | None = None,
    ) -> None:
        self._store = store
        self._obs = observability or NoOpObservability()
        # In-process one-shot tracking. Durable consumption/TTL is feature 010.
        self._consumed: set[str] = set()

    def _validate(
        self,
        repository: RepositoryIdentity,
        decision: ApprovedReviewDecision | None,
        *,
        expected_fingerprint: str,
        content_hash: str | None = None,
    ) -> ApprovedReviewDecision:
        if decision is None or not decision.approved:
            raise ApprovalRequiredError(
                "An approved ReviewDecision is required to mutate the graph."
            )
        if decision.repository != repository:
            raise DecisionRepositoryMismatchError(
                "Approved decision is scoped to a different repository."
            )
        if content_hash is not None and decision.adr_draft_content_hash != content_hash:
            raise DraftContentMismatchError(
                "Content changed since approval; a fresh review is required."
            )
        if decision.target_fingerprint != expected_fingerprint:
            raise MutationFingerprintMismatchError(
                "Approved decision does not authorize this mutation target."
            )
        if decision.decision_id in self._consumed:
            raise DecisionAlreadyConsumedError(
                "This approved decision has already been consumed."
            )
        return decision

    def _consume(self, decision: ApprovedReviewDecision) -> None:
        self._consumed.add(decision.decision_id)

    def _emit(
        self,
        event: str,
        repository: RepositoryIdentity,
        decision: ApprovedReviewDecision,
        **extra: object,
    ) -> None:
        # Metadata-only payload: identifiers, keys, counts — never raw content.
        metadata: dict[str, object] = {
            "repository": repository.key,
            "decision_id": decision.decision_id,
            "decision_version": decision.decision_version,
        }
        metadata.update(extra)
        self._obs.record_event(event, metadata)

    # ----------------------------------------------------------------- writes
    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision | None,
    ) -> NodeId:
        dec = self._validate(
            repository,
            decision,
            expected_fingerprint=upsert_fingerprint(repository, adr),
            content_hash=adr.content_hash,
        )
        node = self._store.upsert_adr_node(repository, adr, dec)
        self._consume(dec)
        self._emit("graph.adr_node_upserted", repository, dec, adr_id=adr.adr_id)
        return node

    def add_relationship(
        self,
        repository: RepositoryIdentity,
        from_node: NodeId,
        to_node: NodeId,
        relationship: RelationshipType,
        decision: ApprovedReviewDecision | None,
    ) -> GraphEdge:
        dec = self._validate(
            repository,
            decision,
            expected_fingerprint=relationship_fingerprint(
                repository, from_node, to_node, relationship
            ),
        )
        edge = self._store.add_relationship(
            repository, from_node, to_node, relationship, dec
        )
        self._consume(dec)
        self._emit(
            "graph.relationship_added",
            repository,
            dec,
            relationship=str(relationship),
        )
        return edge

    def record_structural_change(
        self,
        repository: RepositoryIdentity,
        change: StructuralChange,
        linked_adr: NodeId,
        decision: ApprovedReviewDecision | None,
    ) -> NodeId:
        dec = self._validate(
            repository,
            decision,
            expected_fingerprint=structural_change_fingerprint(
                repository, change, linked_adr
            ),
        )
        node = self._store.record_structural_change(
            repository, change, linked_adr, dec
        )
        self._consume(dec)
        self._emit(
            "graph.structural_change_recorded",
            repository,
            dec,
            change_id=change.change_id,
        )
        return node

    def supersede_adr(
        self,
        repository: RepositoryIdentity,
        prior_adr: NodeId,
        superseding_adr: NodeId,
        decision: ApprovedReviewDecision | None,
        reason: str,
    ) -> GraphEdge:
        dec = self._validate(
            repository,
            decision,
            expected_fingerprint=supersede_fingerprint(
                repository, prior_adr, superseding_adr
            ),
        )
        edge = self._store.supersede_adr(
            repository, prior_adr, superseding_adr, dec, reason
        )
        self._consume(dec)
        self._emit("graph.adr_superseded", repository, dec)
        return edge

    def retract_adr(
        self,
        repository: RepositoryIdentity,
        adr: NodeId,
        decision: ApprovedReviewDecision | None,
        reason: str,
    ) -> GraphEdge:
        dec = self._validate(
            repository,
            decision,
            expected_fingerprint=retract_fingerprint(repository, adr),
        )
        edge = self._store.retract_adr(repository, adr, dec, reason)
        self._consume(dec)
        self._emit("graph.adr_retracted", repository, dec)
        return edge

    def migrate_schema(
        self,
        repository: RepositoryIdentity,
        target_version: SchemaVersion,
        decision: ApprovedReviewDecision | None,
    ) -> MigrationResult:
        dec = self._validate(
            repository,
            decision,
            expected_fingerprint=migrate_fingerprint(repository, target_version),
        )
        result = self._store.migrate_schema(repository, target_version, dec)
        self._consume(dec)
        self._emit(
            "graph.schema_migrated",
            repository,
            dec,
            target_version=target_version.label,
        )
        return result


__all__ = [
    "ApprovalBoundMutationService",
    "upsert_fingerprint",
    "relationship_fingerprint",
    "structural_change_fingerprint",
    "supersede_fingerprint",
    "retract_fingerprint",
    "migrate_fingerprint",
]
