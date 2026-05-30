"""Core smoke-depth domain models for the LivingADR walking skeleton.

These models are intentionally minimal. They capture the repository-scoped shapes
needed to prove the end-to-end seam (event -> change/evidence -> draft -> approval
-> approved record -> why answer) without committing to production field surfaces.
Detailed/production fields are deferred to later features (002-015).

Source-of-truth discipline (architecture #data-model, #anti-patterns):
- ``ChangeEvidence`` is immutable evidence gathered from the PR fixture.
- ``ADRDraft`` is provisional and never authoritative.
- ``ADRRecord`` is the authoritative approved rationale.
- Every record carries ``repository`` scope.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RepositoryIdentity(BaseModel):
    """Stable repository key: ``host/owner/repo`` plus an opaque provider id."""

    model_config = ConfigDict(frozen=True)

    host: str
    owner: str
    repo: str
    repo_id: str

    @property
    def key(self) -> str:
        return f"{self.host}/{self.owner}/{self.repo}"


class SCMEvent(BaseModel):
    """Normalized, idempotent merged-PR-like event envelope (smoke depth)."""

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    delivery_id: str
    provider: str
    event_type: str
    pr_number: int
    pr_title: str
    merged_at: datetime
    diff_summary: str
    changed_files: tuple[str, ...]


class ChangeEvidence(BaseModel):
    """Immutable evidence gathered from a merged PR (smoke depth).

    Evidence is stored separately from inferred rationale (architecture
    #data-model, FM-06). It is never authoritative on its own.
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    evidence_id: str
    source_delivery_id: str
    pr_number: int
    diff_summary: str
    changed_files: tuple[str, ...]


class StructuralChange(BaseModel):
    """A classified architecture-significant change (smoke depth).

    Links to the source PR evidence and later to the approved ADR node.
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    change_id: str
    change_type: str
    summary: str
    evidence_id: str


class ADRDraft(BaseModel):
    """Provisional ADR draft (smoke depth). Never authoritative until approved.

    ``is_stub`` and the rendered markdown make it explicit that this is
    deterministic smoke output, not production Claude-authored rationale
    (architecture #anti-patterns FM-06/FM-23).
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    draft_id: str
    structural_change_id: str
    status: str
    title: str
    context: str
    decision: str
    consequences: str
    alternatives: str
    citations: tuple[str, ...]
    rendered_markdown: str
    is_stub: bool = True


class ApprovalEvent(BaseModel):
    """Human approve/edit/reject event (smoke depth: accept-only).

    Stores reviewer identity and decision provenance even when author and
    reviewer are the same person (FM-05: decision ownership).
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    reviewer_id: str
    adr_draft_id: str
    action: str  # "approve" only in the smoke skeleton


class ApprovedReviewDecision(BaseModel):
    """Capability object minted only by an approved review (smoke depth).

    Mirrors the architecture capability shape at minimal depth: it binds the
    reviewer, the exact reviewed draft (via SHA-256 content hash), the structural
    change, and the repository scope. Only an approved event mints this; it is
    required to authorize any authoritative ADR persistence.
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    decision_id: str
    reviewer_id: str
    adr_draft_id: str
    adr_draft_content_hash: str
    structural_change_event_id: str
    minted_at: datetime
    approved: bool = True
    is_stub: bool = True
