"""Graph context packaging for ADR drafting (feature 008, slice S-003, US-2).

Assembles *approved* architecture context for a draft prompt using **only**
feature 007's read-only :class:`~living_adr.core.graph.ports.ArchitectureContextQuery`
port. Calls are repository-scoped and bounded (``max_depth``/``limit``), citations
are reduced to bounded ADR ids (never backend objects), absent context is marked
explicitly so the prompt can label rationale provisional (US-2), and ordering is
deterministic for identical inputs (NFR-3).

No write port, LlamaIndex, store, or SCM type is imported here (intent
#contract-bindings): the packer is a pure consumer of the read port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from living_adr.core.adr_draft import CitationKind, DraftCitation
from living_adr.core.graph.models import ADRPath, RelationshipType, WhyAnswer
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.structural_change import StructuralChange

#: Bounded traversal/answer limits (architecture #cross-cutting: bounded reads).
DEFAULT_CONTEXT_MAX_DEPTH = 2
DEFAULT_CONTEXT_LIMIT = 5

#: Explicit marker emitted when no approved context is available (US-2).
NO_APPROVED_CONTEXT_MARKER = (
    "No approved architecture context was found for this change; "
    "rationale below is provisional."
)


@runtime_checkable
class ContextQuery(Protocol):
    """Structural subset of feature 007's read port the packer depends on."""

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = ...,
        snapshot: object | None = ...,
        limit: int = ...,
    ) -> WhyAnswer: ...

    def traverse_from_code_area(
        self,
        repository: RepositoryIdentity,
        code_area_id: str,
        relationship_types: set[RelationshipType] | None = ...,
        max_depth: int = ...,
        snapshot: object | None = ...,
    ) -> list[ADRPath]: ...


class ContextRequest(BaseModel):
    """A repository-scoped, bounded request for approved context."""

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    code_area_id: str
    question: str
    max_depth: int = DEFAULT_CONTEXT_MAX_DEPTH
    limit: int = DEFAULT_CONTEXT_LIMIT


class GraphContextItem(BaseModel):
    """One bounded, string-only context item (no backend objects)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    summary: str
    adr_ids: tuple[str, ...] = ()


class PackagedContext(BaseModel):
    """Bounded, deterministic, citation-only approved context for a prompt."""

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    question: str
    items: tuple[GraphContextItem, ...] = ()
    citations: tuple[DraftCitation, ...] = ()
    is_empty: bool = True
    empty_marker: str | None = None


def build_context_request(change: StructuralChange) -> ContextRequest:
    """Derive a deterministic, bounded context request from a structural change."""

    code_area_id = sorted(change.source_paths)[0] if change.source_paths else ""
    subject = change.affected_dependency or change.change_type.value
    question = (
        f"Why was {subject} {change.operation.value} "
        f"in {change.repository.key}?"
    )
    return ContextRequest(
        repository=change.repository,
        code_area_id=code_area_id,
        question=question,
    )


def package_architecture_context(
    query: ContextQuery, request: ContextRequest
) -> PackagedContext:
    """Package approved context via the read port into bounded citations.

    Makes exactly one ``answer_why`` and one ``traverse_from_code_area`` call,
    both repository-scoped and bounded by the request. Extracts ADR citation ids
    (deduplicated, sorted), marks empty context explicitly, and never returns a
    backend object.
    """

    why = query.answer_why(
        request.repository,
        request.question,
        code_area_id=request.code_area_id,
        limit=request.limit,
    )
    paths = query.traverse_from_code_area(
        request.repository,
        request.code_area_id,
        max_depth=request.max_depth,
    )

    items: list[GraphContextItem] = []
    adr_ids: set[str] = set()

    if why.found and (why.answer.strip() or why.adr_id):
        why_adr_ids = tuple(
            sorted({c for c in why.citations} | ({why.adr_id} if why.adr_id else set()))
        )
        adr_ids.update(why_adr_ids)
        items.append(
            GraphContextItem(
                kind="why",
                summary=why.answer.strip(),
                adr_ids=why_adr_ids,
            )
        )

    for path in paths:
        path_adr_ids = tuple(sorted({ref.adr_id for ref in path.adrs}))
        if not path_adr_ids:
            continue
        adr_ids.update(path_adr_ids)
        titles = ", ".join(sorted({ref.title for ref in path.adrs}))
        items.append(
            GraphContextItem(
                kind="path",
                summary=f"Related approved ADRs for {path.code_area_id}: {titles}",
                adr_ids=path_adr_ids,
            )
        )

    citations = tuple(
        DraftCitation(kind=CitationKind.ADR, ref=ref) for ref in sorted(adr_ids)
    )
    is_empty = not items
    return PackagedContext(
        repository=request.repository,
        question=request.question,
        items=tuple(items),
        citations=citations,
        is_empty=is_empty,
        empty_marker=NO_APPROVED_CONTEXT_MARKER if is_empty else None,
    )


__all__ = [
    "DEFAULT_CONTEXT_MAX_DEPTH",
    "DEFAULT_CONTEXT_LIMIT",
    "NO_APPROVED_CONTEXT_MARKER",
    "ContextQuery",
    "ContextRequest",
    "GraphContextItem",
    "PackagedContext",
    "build_context_request",
    "package_architecture_context",
]
