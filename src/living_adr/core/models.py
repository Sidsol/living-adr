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
