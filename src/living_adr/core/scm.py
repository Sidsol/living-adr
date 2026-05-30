"""Provider-neutral SCM contracts: events, fetch handles, provider port (003).

These are the cross-feature seams established by feature 003 and reused by
classifiers (004/005), publish-back (011), and onboarding (014). They are
deliberately provider-neutral so a future Azure DevOps adapter maps into the same
workflow-facing shape (architecture #service-boundaries, FM-24).

Relationship to the canonical :class:`~living_adr.core.models.SCMEvent`
----------------------------------------------------------------------
Feature 001 established ``SCMEvent`` as the canonical normalized merged-PR event.
Ingestion **emits that exact contract** — it is never redefined here. The richer
normalization data that does not belong on the minimal event (the repository-
scoped normalized PR key, provider-neutral fetch handles, opaque provider
metadata) is carried by :class:`SCMEventEnvelope`, which *wraps* the canonical
event. Changed-file/diff content is evidence, not part of the event, and lives in
:class:`CandidateEvidence` produced after the provider fetch (slice 4).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from living_adr.core.ingestion import IngestionErrorCategory
from living_adr.core.models import SCMEvent
from living_adr.core.repository import RepositoryIdentity


class SCMProviderName(StrEnum):
    """Supported / planned SCM providers. GitHub is implemented; ADO is a seam."""

    GITHUB = "github"
    AZURE_DEVOPS = "azure_devops"


def build_normalized_pr_key(
    provider: SCMProviderName,
    repository: RepositoryIdentity,
    pr_number: int,
    merge_commit_sha: str | None,
) -> str:
    """Repository-scoped, provider-neutral pull-request identity.

    PR numbers collide across repositories/providers, so the key binds provider +
    canonical repository key + PR number + merge commit SHA (architecture
    #anti-patterns: never use PR number alone as an idempotency key).
    """

    sha = merge_commit_sha or "unknown"
    return f"{provider.value}:{repository.key}:{pr_number}:{sha}"


class SCMFetchHandle(BaseModel):
    """Provider-neutral coordinates used to fetch PR metadata, files, and diff.

    Carries no secrets: the ``installation_id`` is an opaque reference resolved to
    credentials by the adapter, never a token.
    """

    model_config = ConfigDict(frozen=True)

    installation_id: str
    pr_number: int
    head_sha: str | None = None
    head_ref: str | None = None
    base_ref: str | None = None
    merge_commit_sha: str | None = None


class SCMEventEnvelope(BaseModel):
    """Canonical :class:`SCMEvent` plus provider-neutral normalization context."""

    model_config = ConfigDict(frozen=True)

    event: SCMEvent
    provider: SCMProviderName
    provider_event_type: str
    normalized_pr_key: str
    fetch_handle: SCMFetchHandle
    sender: str | None = None
    # Opaque provider-specific data kept out of workflow-facing fields (FM-24).
    provider_metadata: Mapping[str, str] = {}


class PullRequestMetadata(BaseModel):
    """Minimal PR metadata fetched through the provider (V1 classifier input)."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    body: str
    author: str | None
    state: str
    merged: bool
    head_ref: str | None
    base_ref: str | None
    merge_commit_sha: str | None


class ChangedFileMetadata(BaseModel):
    """One changed file's metadata (filename + status + line deltas)."""

    model_config = ConfigDict(frozen=True)

    filename: str
    status: str
    additions: int = 0
    deletions: int = 0


class DiffEvidence(BaseModel):
    """Diff handle/summary. Raw diff text is never exported to observability."""

    model_config = ConfigDict(frozen=True)

    diff_handle: str
    summary: str
    truncated: bool = False
    byte_size: int | None = None


class InstallationStatus(StrEnum):
    """Outcome of verifying a GitHub App installation for a repository (014).

    Provider-neutral so onboarding diagnostics never depend on raw GitHub HTTP
    status codes. The GitHub adapter maps API results into these values.
    """

    INSTALLED = "installed"
    NOT_INSTALLED = "not_installed"
    SUSPENDED = "suspended"
    MISMATCHED = "mismatched"
    ACCESS_DENIED = "access_denied"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


class InstallationVerification(BaseModel):
    """Safe result of an installation check: status + non-secret metadata only.

    Carries no tokens or private key material — only the repository key, the
    expected/actual installation ids, repo id, default branch, and the granted
    permission map (e.g. ``{"contents": "read"}``) needed for onboarding
    diagnostics (architecture #cross-cutting, FM-21).
    """

    model_config = ConfigDict(frozen=True)

    repository_key: str
    expected_installation_id: str
    status: InstallationStatus
    installation_id: str | None = None
    repo_id: str | None = None
    default_branch: str | None = None
    permissions: Mapping[str, str] = {}

    @property
    def is_installed(self) -> bool:
        return self.status is InstallationStatus.INSTALLED


class CandidateEvidence(BaseModel):
    """Immutable evidence bundle for classifiers, linked to the source event.

    Evidence is *not* approved rationale (architecture #anti-patterns); it is the
    immutable PR/diff input a downstream classifier reasons over.
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    source_delivery_id: str
    normalized_pr_key: str
    pr_number: int
    pr_title: str
    changed_files: tuple[ChangedFileMetadata, ...]
    diff: DiffEvidence
    provider: SCMProviderName
    is_complete: bool = True


@runtime_checkable
class SCMProvider(Protocol):
    """Provider-neutral port for fetching minimal PR metadata, files, and diff."""

    def fetch_pull_request(
        self, repository: RepositoryIdentity, handle: SCMFetchHandle
    ) -> PullRequestMetadata: ...

    def fetch_changed_files(
        self, repository: RepositoryIdentity, handle: SCMFetchHandle
    ) -> tuple[ChangedFileMetadata, ...]: ...

    def fetch_diff(
        self, repository: RepositoryIdentity, handle: SCMFetchHandle
    ) -> DiffEvidence: ...


class RepositoryFile(BaseModel):
    """One entry in a repository directory listing (provider-neutral).

    ``sha`` is the blob/object id used as the optimistic-concurrency token when
    updating an existing file; ``type`` distinguishes files from sub-directories.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    path: str
    sha: str | None = None
    type: str = "file"


class FileContent(BaseModel):
    """Decoded contents of a single repository file plus its concurrency token."""

    model_config = ConfigDict(frozen=True)

    path: str
    text: str
    sha: str | None = None


class CommitResult(BaseModel):
    """Outcome of a single-file commit through the contents port."""

    model_config = ConfigDict(frozen=True)

    commit_sha: str
    path: str
    content_sha: str | None = None
    created: bool = True


@runtime_checkable
class SCMContentsProvider(Protocol):
    """Provider-neutral port for reading a directory and committing one ADR file.

    Publish-back (feature 011) depends only on this narrow port; GitHub REST
    details live in the adapter. Methods are minimal-access (FM-18): a single
    directory listing, single-file reads, and a single-file create/update.
    """

    def list_directory(
        self, repository: RepositoryIdentity, branch: str, directory: str
    ) -> tuple[RepositoryFile, ...]: ...

    def read_file(
        self, repository: RepositoryIdentity, branch: str, path: str
    ) -> FileContent | None: ...

    def create_file(
        self,
        repository: RepositoryIdentity,
        branch: str,
        path: str,
        content: str,
        message: str,
        *,
        sha: str | None = None,
    ) -> CommitResult: ...


class SCMProviderError(Exception):
    """Base class for provider fetch failures, carrying an error category."""

    category: IngestionErrorCategory = IngestionErrorCategory.UNKNOWN


class RateLimitError(SCMProviderError):
    category = IngestionErrorCategory.RATE_LIMITED


class ProviderPermissionError(SCMProviderError):
    category = IngestionErrorCategory.PERMISSION_DENIED


class ResourceNotFoundError(SCMProviderError):
    category = IngestionErrorCategory.RESOURCE_NOT_FOUND


class TransientProviderError(SCMProviderError):
    category = IngestionErrorCategory.TRANSIENT


class CommitConflictError(SCMProviderError):
    """Optimistic-concurrency failure committing a file (branch head moved).

    Categorized as TRANSIENT so publish-back may refresh state and retry within
    a bounded budget before dead-lettering.
    """

    category = IngestionErrorCategory.TRANSIENT


def category_for_error(error: Exception) -> IngestionErrorCategory:
    """Map a provider exception to an ingestion error category."""

    if isinstance(error, SCMProviderError):
        return error.category
    return IngestionErrorCategory.UNKNOWN


__all__ = [
    "SCMProviderName",
    "build_normalized_pr_key",
    "SCMFetchHandle",
    "SCMEventEnvelope",
    "PullRequestMetadata",
    "ChangedFileMetadata",
    "DiffEvidence",
    "InstallationStatus",
    "InstallationVerification",
    "CandidateEvidence",
    "SCMProvider",
    "RepositoryFile",
    "FileContent",
    "CommitResult",
    "SCMContentsProvider",
    "SCMProviderError",
    "RateLimitError",
    "ProviderPermissionError",
    "ResourceNotFoundError",
    "TransientProviderError",
    "CommitConflictError",
    "category_for_error",
]
