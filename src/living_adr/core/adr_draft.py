"""Provisional ADR draft contract (feature 008, slice S-001).

Feature 008 turns a Claude completion into a **provisional**, non-authoritative
draft. This module defines that draft DTO and its supporting value objects:

* :class:`DraftCitation` — a bounded citation to either immutable
  :class:`~living_adr.core.structural_change.ChangeEvidence` (``EVIDENCE``) or an
  approved ADR surfaced through feature 007's read port (``ADR``).
* :class:`ModelMetadata` — provider/token metadata kept *out* of the content
  hash so identical drafting inputs hash identically (NFR-3).
* :class:`ADRDraft` — the provisional draft itself; ``provisional`` is always
  ``True`` until a downstream HITL approval (features 009/010) makes it
  authoritative.
* :class:`DraftADRRecordCandidate` — a projection toward feature 006's
  ``ADRRecord`` shape that is deliberately *not* an authoritative record: it
  carries no ``decision_id`` and stays ``proposed``/provisional.

Determinism (NFR-3): :func:`compute_draft_content_hash` is a pure SHA-256 over
the canonical draft body and sorted citation refs only — never provider/token
metadata, clocks, or randomness.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from living_adr.core.adr import ADRStatus
from living_adr.core.repository import RepositoryIdentity


class DraftingOutcome(StrEnum):
    """The typed terminal outcome of a drafting attempt (FR-9).

    Exactly one of these classifies any draft-node invocation. Only ``DRAFTED``
    yields an :class:`ADRDraft`; every other value is a recorded, metadata-safe
    non-draft outcome that performed **no** authoritative mutation.
    """

    DRAFTED = "drafted"
    NO_ADR_NEEDED = "no_adr_needed"
    LLM_POLICY_DENIED = "llm_policy_denied"
    BUDGET_EXCEEDED = "budget_exceeded"
    MISSING_EVIDENCE = "missing_evidence"
    PROVIDER_ERROR = "provider_error"
    INVALID_OUTPUT = "invalid_output"


class CitationKind(StrEnum):
    """What a :class:`DraftCitation` points at."""

    EVIDENCE = "evidence"
    ADR = "adr"


class DraftCitation(BaseModel):
    """A bounded citation: an evidence id or an approved-ADR id, plus a label."""

    model_config = ConfigDict(frozen=True)

    kind: CitationKind
    ref: str
    label: str = ""

    @field_validator("ref")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("citation ref must not be empty or whitespace")
        return stripped


class ModelMetadata(BaseModel):
    """Provider/token metadata for one completion (excluded from the hash)."""

    model_config = ConfigDict(frozen=True)

    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    latency_ms: int | None = None


def _digest(*parts: object) -> str:
    canonical = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_draft_content_hash(
    *,
    repository: RepositoryIdentity,
    structural_change_id: str,
    title: str,
    context: str,
    decision: str,
    alternatives: str,
    consequences: str,
    citations: Iterable[DraftCitation],
) -> str:
    """Deterministic SHA-256 over the draft body + sorted citation refs.

    Provider/token metadata is intentionally excluded so two drafts produced from
    identical inputs (but different provider runs) hash identically (NFR-3).
    """

    citation_part = ":".join(
        sorted(f"{c.kind.value}={c.ref}" for c in citations)
    )
    return _digest(
        repository.key,
        structural_change_id,
        title,
        context,
        decision,
        alternatives,
        consequences,
        citation_part,
    )


class ADRDraft(BaseModel):
    """A provisional, non-authoritative Markdown ADR draft (FR-8).

    The draft is **never** authoritative: ``provisional`` stays ``True`` until a
    human approval downstream mints an authoritative ``ADRRecord``. The
    ``content_hash`` binds the draft to its exact reviewed body.
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    draft_id: str
    structural_change_id: str
    title: str
    status: str = "proposed"
    context: str
    decision: str
    alternatives: str
    consequences: str
    citations: tuple[DraftCitation, ...] = ()
    rendered_markdown: str
    model_metadata: ModelMetadata | None = None
    content_hash: str
    provisional: bool = True

    @field_validator("draft_id", "content_hash")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return stripped

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        """Evidence citation refs in declaration order."""

        return tuple(
            c.ref for c in self.citations if c.kind is CitationKind.EVIDENCE
        )

    @property
    def adr_citation_ids(self) -> tuple[str, ...]:
        """Approved-ADR citation refs in declaration order."""

        return tuple(c.ref for c in self.citations if c.kind is CitationKind.ADR)

    def to_record_candidate(self) -> DraftADRRecordCandidate:
        """Project toward the feature-006 ``ADRRecord`` shape, non-authoritatively.

        The result is deliberately *not* an ``ADRRecord``: it carries no approved
        ``decision_id`` and stays ``proposed``/provisional. An authoritative
        record is only minted downstream after HITL approval.
        """

        return DraftADRRecordCandidate(
            repository=self.repository,
            adr_id=self.draft_id,
            title=self.title,
            status=ADRStatus.PROPOSED,
            content_hash=self.content_hash,
            structural_change_id=self.structural_change_id,
            evidence_ids=self.evidence_ids,
            markdown=self.rendered_markdown,
            provisional=True,
        )


class DraftADRRecordCandidate(BaseModel):
    """A provisional projection toward an authoritative ``ADRRecord``.

    Intentionally distinct from :class:`living_adr.core.adr.ADRRecord`: it has no
    ``decision_id`` field (no approval linkage) and is always ``PROPOSED`` /
    provisional, so it can never be mistaken for an approved record.
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    adr_id: str
    title: str
    status: ADRStatus = ADRStatus.PROPOSED
    content_hash: str
    structural_change_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    markdown: str = ""
    provisional: bool = True


__all__ = [
    "DraftingOutcome",
    "CitationKind",
    "DraftCitation",
    "ModelMetadata",
    "ADRDraft",
    "DraftADRRecordCandidate",
    "compute_draft_content_hash",
]
