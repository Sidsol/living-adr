"""ADR publish-back package (feature 011).

Publishes a human-approved :class:`~living_adr.core.adr.ADRRecord` back to the
source GitHub repository when ``RepositoryConfig.adr_publication_policy`` enables
it. Publication is authorised only through feature 010's approval boundary
(``DurableApprovalBoundMutationService`` / the same just-in-time validation it
uses) and performed only through feature 003's SCM provider seam. Every
publication is linked to its authorising ``decision_id`` for SM-05 audit and is
idempotent for retries of the same approved decision.

Public symbols are re-exported lazily by submodule to keep import side effects
minimal; import the concrete module (``models``, ``service`` …) directly.
"""

from __future__ import annotations

__all__: list[str] = []
