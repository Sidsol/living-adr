"""Publication domain models, fingerprints, and typed errors (feature 011).

These are pure, provider-free DTOs shared by the publication service, repository,
numbering, and workflow handoff. They carry **no secrets and no raw ADR bodies in
observability metadata**; the ADR Markdown is committed to GitHub but is never
exported to the observability port (NFR-4; architecture #cross-cutting).

Source-of-truth discipline: an :class:`~living_adr.core.adr.ADRRecord` is the
authoritative rationale; publication merely writes a derived Markdown projection
of it back to the source repository. Repository scope is always explicit — a
target repository is never inferred from ADR content (NFR-5).
"""

from __future__ import annotations

import hashlib
import posixpath
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from living_adr.core.adr import ADRRecord
from living_adr.core.approval import ApprovalError, ApprovedReviewDecision
from living_adr.core.config import PublicationPolicy
from living_adr.core.repository import RepositoryIdentity

#: Default ADR path template (POSIX, relative). ``NNNN`` is the zero-padded
#: number token and ``<slug>`` the title slug (architecture #data-model; FR-5).
DEFAULT_ADR_PATH_TEMPLATE = "docs/adr/NNNN-<slug>.md"


# --- typed errors ---------------------------------------------------------


class PublicationError(ApprovalError):
    """Base class for publish-back failures (extends the approval hierarchy)."""


class PublicationRepositoryMismatchError(PublicationError):
    """Raised when the ADR/decision repository differs from the publish scope."""


class PublicationNotAuthorizedError(PublicationError):
    """Raised when no valid, feature-010-consumed approval authorises publish."""


class PublicationTargetMismatchError(PublicationError):
    """Raised when a same-``decision_id`` retry presents a different target."""


class PublicationConflictExhaustedError(PublicationError):
    """Raised when bounded refresh-and-retry cannot resolve a commit conflict."""


# --- status / target / records --------------------------------------------


class PublicationStatus(StrEnum):
    """Outcome of one publish-back attempt (audit-friendly, exhaustive)."""

    PENDING = "pending"
    COMMITTED = "committed"
    SKIPPED_BY_POLICY = "skipped_by_policy"
    ALREADY_PUBLISHED = "already_published"
    DEAD_LETTERED = "dead_lettered"

    @property
    def is_terminal_success(self) -> bool:
        """True for outcomes that represent a satisfied publication request."""

        return self in (
            PublicationStatus.COMMITTED,
            PublicationStatus.SKIPPED_BY_POLICY,
            PublicationStatus.ALREADY_PUBLISHED,
        )


class ADRPublicationTarget(BaseModel):
    """Resolved, repository-scoped publish target derived from config (FR-5)."""

    model_config = ConfigDict(frozen=True)

    repository_key: str
    branch: str
    path_template: str
    directory: str
    padding_width: int = 4
    publishes_to_github: bool = True

    @field_validator("repository_key", "branch", "path_template")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return stripped


class ADRPublicationRequest(BaseModel):
    """An approved ADR publish-back request bound to one repository scope."""

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    adr: ADRRecord
    decision: ApprovedReviewDecision | None
    policy: PublicationPolicy
    target: ADRPublicationTarget

    @model_validator(mode="after")
    def _scope_consistency(self) -> ADRPublicationRequest:
        # NFR-5: repository scope is explicit; the ADR and the (approved)
        # decision must both match the publish scope — never inferred.
        if self.adr.repository != self.repository:
            raise PublicationRepositoryMismatchError(
                "ADR record repository does not match the publication scope"
            )
        if self.decision is not None and self.decision.repository != self.repository:
            raise PublicationRepositoryMismatchError(
                "approved decision repository does not match the publication scope"
            )
        if self.target.repository_key != self.repository.key:
            raise PublicationRepositoryMismatchError(
                "publication target repository does not match the publication scope"
            )
        return self


class PublicationRecord(BaseModel):
    """Durable publication intent/result keyed by ``decision_id`` (FR-8).

    Reserved before the remote write and finalised after; the ``fingerprint``
    field is the idempotency key feature 011 compares same-``decision_id``
    retries against.
    """

    model_config = ConfigDict(frozen=True)

    decision_id: str
    repository_key: str
    adr_record_id: str
    content_hash: str
    fingerprint: str
    target_branch: str
    status: PublicationStatus
    target_path: str | None = None
    commit_sha: str | None = None
    detail: str = ""

    @field_validator("decision_id", "fingerprint")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return stripped


class ADRPublicationResult(BaseModel):
    """Return value of a publish-back attempt (metadata-only; no raw body)."""

    model_config = ConfigDict(frozen=True)

    status: PublicationStatus
    decision_id: str
    repository_key: str
    adr_record_id: str
    content_hash: str
    target_branch: str
    target_path: str | None = None
    commit_sha: str | None = None
    idempotent: bool = False
    detail: str = ""

    @classmethod
    def from_record(
        cls, record: PublicationRecord, *, idempotent: bool = False
    ) -> ADRPublicationResult:
        return cls(
            status=record.status,
            decision_id=record.decision_id,
            repository_key=record.repository_key,
            adr_record_id=record.adr_record_id,
            content_hash=record.content_hash,
            target_branch=record.target_branch,
            target_path=record.target_path,
            commit_sha=record.commit_sha,
            idempotent=idempotent,
            detail=record.detail,
        )


# --- fingerprint ----------------------------------------------------------


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def publication_fingerprint(
    repository: RepositoryIdentity,
    adr: ADRRecord,
    target: ADRPublicationTarget,
    policy: PublicationPolicy,
    decision_id: str,
) -> str:
    """Deterministic publish target fingerprint (FR-9; T011-S1-003).

    Binds repository, ADR record id, approved content hash, publication policy,
    target branch, path template, and the authorising ``decision_id`` so a
    same-``decision_id`` retry with a drifted content/path/branch/policy is
    detected as a target mismatch.
    """

    return _fingerprint(
        "publish_adr",
        repository.key,
        adr.adr_id,
        adr.content_hash,
        policy.value,
        target.branch,
        target.path_template,
        decision_id,
    )


def adr_directory(path_template: str) -> str:
    """POSIX directory portion of an ADR path template."""

    return posixpath.dirname(path_template)


__all__ = [
    "DEFAULT_ADR_PATH_TEMPLATE",
    "PublicationError",
    "PublicationRepositoryMismatchError",
    "PublicationNotAuthorizedError",
    "PublicationTargetMismatchError",
    "PublicationConflictExhaustedError",
    "PublicationStatus",
    "ADRPublicationTarget",
    "ADRPublicationRequest",
    "PublicationRecord",
    "ADRPublicationResult",
    "publication_fingerprint",
    "adr_directory",
]
