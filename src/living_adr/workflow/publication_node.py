"""Approval-bound ADR publish-back workflow handoff (feature 011, slice S011-05).

:class:`PublicationHandoffNode` runs *after* the approval-bound mutation has
performed the authoritative graph write. It reuses the deterministic ADR record
builder (the exact record the approval covered), resolves the repository-scoped
:class:`RepositoryConfig`, and routes the approved ADR through the single
:class:`ADRPublicationService` publish entry point.

The node is a side-effect-only handoff: it returns an **empty** state update so it
adds no fields to the frozen, ``extra="forbid"`` :class:`WorkflowState` (the
publish outcome is durable in the publication repository + audit, not on graph
state). It performs no publish when no authoritative mutation occurred or the
repository is unconfigured — never reaching past the approval boundary.
"""

from __future__ import annotations

from collections.abc import Callable

from living_adr.core.config import RepositoryConfig
from living_adr.core.repository import RepositoryIdentity
from living_adr.publication.models import ADRPublicationRequest, ADRPublicationResult
from living_adr.publication.service import (
    ADRPublicationService,
    resolve_publication_target,
)
from living_adr.workflow.nodes.protocols import StateUpdate
from living_adr.workflow.nodes.stubs import StubMutationHandoffNode
from living_adr.workflow.state import MutationOutcome, WorkflowState

ConfigProvider = Callable[[RepositoryIdentity], RepositoryConfig | None]


class PublicationHandoffNode:
    """Post-mutation handoff that publishes the approved ADR (US-5 → publish)."""

    def __init__(
        self,
        *,
        service: ADRPublicationService,
        config_provider: ConfigProvider,
        record_builder: StubMutationHandoffNode | None = None,
    ) -> None:
        self._service = service
        self._config_provider = config_provider
        self._builder = record_builder or StubMutationHandoffNode()

    def publish_for_state(self, state: WorkflowState) -> ADRPublicationResult | None:
        """Publish the approved ADR for ``state`` if an authoritative write ran.

        Returns ``None`` (no publish) when the mutation did not occur, the
        decision is absent, or the repository is unconfigured.
        """

        if state.repository is None or state.draft is None:
            return None
        decision = state.approved_decision
        if decision is None or not decision.approved:
            return None
        mutation = state.mutation_result
        if mutation is None or mutation.outcome is not MutationOutcome.MUTATED:
            return None
        config = self._config_provider(state.repository)
        if config is None:
            return None

        adr = self._builder.build_adr_record(state)
        request = ADRPublicationRequest(
            repository=state.repository,
            adr=adr,
            decision=decision,
            policy=config.adr_publication_policy,
            target=resolve_publication_target(config),
        )
        return self._service.publish(request)

    def __call__(self, state: WorkflowState) -> StateUpdate:
        # Side-effect-only handoff: durable outcome lives in the publication
        # repository + audit, never on the frozen extra="forbid" graph state.
        self.publish_for_state(state)
        return {}


__all__ = ["PublicationHandoffNode"]
