"""Approval-bound stub store and approved-context query projection.

This is a SMOKE STUB for ``ArchitectureGraphStore`` (write side) and
``ArchitectureContextQuery`` (read side). It proves the safety-critical seam:
no authoritative ``ADRRecord`` may be created without a valid
``ApprovedReviewDecision`` whose content hash matches the exact reviewed draft
(architecture #service-boundaries; SM-05; FM-13). Storage is in-memory and
single-process; later features replace it with a LlamaIndex/SQLite adapter.

The read side is approved-context-only: ``answer_why`` never reads pending drafts
or raw evidence as authoritative rationale (source-of-truth discipline).
"""

from __future__ import annotations

import hashlib

from living_adr.core.models import (
    ADRDraft,
    ADRProvenance,
    ADRRecord,
    ADRRef,
    ApprovedReviewDecision,
    ChangeEvidence,
    RepositoryIdentity,
    SCMEvent,
    StructuralChange,
    WhyAnswer,
)


class UnauthorizedMutationError(PermissionError):
    """Raised when persistence is attempted without a valid approved decision."""


class DraftContentMismatchError(ValueError):
    """Raised when the draft to persist differs from the approved-reviewed draft."""


def _draft_content_hash(draft: ADRDraft) -> str:
    return hashlib.sha256(draft.rendered_markdown.encode("utf-8")).hexdigest()


class ApprovalBoundStubStore:
    """In-memory approval-bound store with an approved-only read projection."""

    def __init__(self) -> None:
        # repository.key -> {adr_id: ADRRecord}
        self._records: dict[str, dict[str, ADRRecord]] = {}
        # consumed decision_id -> adr_id (one-shot idempotency)
        self._consumed: dict[str, str] = {}

    # ------------------------------------------------------------------ write
    def persist_approved_adr(
        self,
        *,
        event: SCMEvent,
        evidence: ChangeEvidence,
        change: StructuralChange,
        draft: ADRDraft,
        decision: ApprovedReviewDecision | None,
    ) -> ADRRecord:
        """Persist exactly one approved ``ADRRecord``, guarding the seam.

        Raises ``UnauthorizedMutationError`` if the decision is missing,
        unapproved, scoped to a different repository/draft; raises
        ``DraftContentMismatchError`` if the draft content drifted since review.
        """

        if decision is None or not decision.approved:
            raise UnauthorizedMutationError(
                "An approved ReviewDecision is required to persist an ADRRecord."
            )

        # Repository scope must agree across the whole provenance chain.
        repos = {
            event.repository,
            evidence.repository,
            change.repository,
            draft.repository,
            decision.repository,
        }
        if len(repos) != 1:
            raise UnauthorizedMutationError(
                "Repository scope mismatch across approval provenance chain."
            )

        if decision.adr_draft_id != draft.draft_id:
            raise UnauthorizedMutationError(
                "Approved decision does not match the draft being persisted."
            )

        # Re-hash the current draft and verify it matches the reviewed content.
        if _draft_content_hash(draft) != decision.adr_draft_content_hash:
            raise DraftContentMismatchError(
                "Draft content changed since approval; a fresh review is required."
            )

        # One-shot idempotency: a legitimate retry returns the prior result.
        if decision.decision_id in self._consumed:
            adr_id = self._consumed[decision.decision_id]
            return self._records[draft.repository.key][adr_id]

        adr_id = "adr-" + decision.decision_id.removeprefix("decision-")
        record = ADRRecord(
            repository=draft.repository,
            adr_id=adr_id,
            title=draft.title,
            status="approved",
            markdown=draft.rendered_markdown,
            content_hash=decision.adr_draft_content_hash,
            provenance=ADRProvenance(
                source_delivery_id=event.delivery_id,
                evidence_id=evidence.evidence_id,
                structural_change_id=change.change_id,
                adr_draft_id=draft.draft_id,
                decision_id=decision.decision_id,
            ),
        )
        self._records.setdefault(draft.repository.key, {})[adr_id] = record
        self._consumed[decision.decision_id] = adr_id
        return record

    # ------------------------------------------------------------------- read
    def list_approved(self, repository: RepositoryIdentity) -> list[ADRRef]:
        """Return approved-ADR references scoped to one repository."""

        records = self._records.get(repository.key, {})
        return [
            ADRRef(
                repository=r.repository,
                adr_id=r.adr_id,
                title=r.title,
                status=r.status,
            )
            for r in records.values()
        ]

    def fetch_adr(
        self, repository: RepositoryIdentity, adr_id: str
    ) -> ADRRecord | None:
        """Fetch one approved ADR record by id within a repository scope."""

        return self._records.get(repository.key, {}).get(adr_id)

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
    ) -> WhyAnswer:
        """Answer a why-question from approved ADR context only.

        Reads only stored approved ``ADRRecord`` data — never pending drafts or
        raw PR evidence. Returns a no-approved-context answer when nothing is
        approved for the repository scope.
        """

        records = list(self._records.get(repository.key, {}).values())
        if not records:
            return WhyAnswer(
                repository=repository,
                question=question,
                answer=(
                    "No approved ADR context is available for this repository. "
                    "Pending drafts and raw PR evidence are not authoritative."
                ),
                adr_id=None,
                citations=(),
                found=False,
            )

        record = records[0]
        return WhyAnswer(
            repository=repository,
            question=question,
            answer=(
                f"Approved decision {record.adr_id}: {record.title}. "
                f"See the approved ADR rationale for details."
            ),
            adr_id=record.adr_id,
            citations=(
                f"adr:{record.adr_id}",
                f"evidence:{record.provenance.evidence_id}",
            ),
            found=True,
        )
