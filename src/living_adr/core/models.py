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

from pydantic import BaseModel, ConfigDict, field_validator


class RepositoryIdentity(BaseModel):
    """Stable repository key: ``host/owner/repo`` plus an opaque provider id.

    Feature 002 hardens this shared seam: every coordinate is stripped and must
    be non-empty so the canonical key is stable across SCM, graph, MCP, and
    observability metadata. This model carries no secrets.
    """

    model_config = ConfigDict(frozen=True)

    host: str
    owner: str
    repo: str
    repo_id: str

    @field_validator("host", "owner", "repo", "repo_id")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return stripped

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


class ADRProvenance(BaseModel):
    """Provenance links binding an approved ADR record to its smoke pipeline."""

    model_config = ConfigDict(frozen=True)

    source_delivery_id: str
    evidence_id: str
    structural_change_id: str
    adr_draft_id: str
    decision_id: str


class ADRRecord(BaseModel):
    """Authoritative approved decision record (smoke depth).

    This is the canonical approved rationale; the graph/query layer is a
    projection over it (architecture #data-model, FM-23 review-gated record).
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    adr_id: str
    title: str
    status: str
    markdown: str
    content_hash: str
    provenance: ADRProvenance


class ADRRef(BaseModel):
    """Lightweight approved-ADR reference for list/query projections."""

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    adr_id: str
    title: str
    status: str


class WhyAnswer(BaseModel):
    """Read-only MCP-style answer derived from approved context only."""

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    question: str
    answer: str
    adr_id: str | None
    citations: tuple[str, ...]
    found: bool
