"""GitHub provider adapter behind the SCMProvider port (feature 003, slice 4).

Implements minimal merged-PR evidence fetches (PR metadata, changed files, diff)
through an injected, fakeable :class:`GitHubClient` seam so tests never touch the
network (NFR-4). GitHub REST/permission details live here; workflow code depends
only on the provider-neutral :class:`~living_adr.core.scm.SCMProvider` port.

Minimal-access discipline (NFR-3, FM-18): only the PR, its changed-file list, and
its diff are fetched. No broad history, commit, or contents mining.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    ChangedFileMetadata,
    DiffEvidence,
    ProviderPermissionError,
    PullRequestMetadata,
    RateLimitError,
    ResourceNotFoundError,
    SCMFetchHandle,
    SCMProviderError,
    TransientProviderError,
)


class GitHubApiError(Exception):
    """Transport-level GitHub API failure carrying the HTTP status code."""

    def __init__(
        self, status: int, message: str = "", *, rate_limited: bool = False
    ) -> None:
        super().__init__(message or f"GitHub API error {status}")
        self.status = status
        self.rate_limited = rate_limited


class GitHubClient(Protocol):
    """Fakeable GitHub transport seam. Real impls own auth + httpx; fakes return
    canned data so no network call occurs in tests."""

    def get_json(self, path: str) -> object: ...

    def get_diff(self, path: str) -> str: ...


def _map_api_error(error: GitHubApiError) -> SCMProviderError:
    """Map a GitHub HTTP status into the provider-neutral error taxonomy."""

    if error.status == 404:
        return ResourceNotFoundError(str(error))
    if error.status == 429 or (error.status == 403 and error.rate_limited):
        return RateLimitError(str(error))
    if error.status == 403:
        return ProviderPermissionError(str(error))
    if error.status >= 500:
        return TransientProviderError(str(error))
    return SCMProviderError(str(error))


class GitHubProvider:
    """SCMProvider implementation for GitHub App installations."""

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    @staticmethod
    def _pr_path(repository: RepositoryIdentity, handle: SCMFetchHandle) -> str:
        return f"/repos/{repository.owner}/{repository.repo}/pulls/{handle.pr_number}"

    def fetch_pull_request(
        self, repository: RepositoryIdentity, handle: SCMFetchHandle
    ) -> PullRequestMetadata:
        try:
            data = self._client.get_json(self._pr_path(repository, handle))
        except GitHubApiError as exc:
            raise _map_api_error(exc) from exc
        if not isinstance(data, Mapping):
            raise TransientProviderError("unexpected PR payload shape")
        user = data.get("user") or {}
        head = data.get("head") or {}
        base = data.get("base") or {}
        return PullRequestMetadata(
            number=int(data.get("number", handle.pr_number)),
            title=str(data.get("title") or ""),
            body=str(data.get("body") or ""),
            author=user.get("login") if isinstance(user, Mapping) else None,
            state=str(data.get("state") or "unknown"),
            merged=bool(data.get("merged")),
            head_ref=head.get("ref") if isinstance(head, Mapping) else None,
            base_ref=base.get("ref") if isinstance(base, Mapping) else None,
            merge_commit_sha=data.get("merge_commit_sha"),
        )

    def fetch_changed_files(
        self, repository: RepositoryIdentity, handle: SCMFetchHandle
    ) -> tuple[ChangedFileMetadata, ...]:
        path = f"{self._pr_path(repository, handle)}/files"
        try:
            data = self._client.get_json(path)
        except GitHubApiError as exc:
            raise _map_api_error(exc) from exc
        if not isinstance(data, Sequence):
            raise TransientProviderError("unexpected changed-files payload shape")
        files: list[ChangedFileMetadata] = []
        for entry in data:
            if not isinstance(entry, Mapping):
                continue
            files.append(
                ChangedFileMetadata(
                    filename=str(entry.get("filename") or ""),
                    status=str(entry.get("status") or "modified"),
                    additions=int(entry.get("additions", 0) or 0),
                    deletions=int(entry.get("deletions", 0) or 0),
                )
            )
        return tuple(files)

    def fetch_diff(
        self, repository: RepositoryIdentity, handle: SCMFetchHandle
    ) -> DiffEvidence:
        path = self._pr_path(repository, handle)
        try:
            diff_text = self._client.get_diff(path)
        except GitHubApiError as exc:
            raise _map_api_error(exc) from exc
        raw = diff_text or ""
        byte_size = len(raw.encode("utf-8"))
        file_count = raw.count("diff --git ")
        summary = f"{file_count} file(s) changed, {byte_size} diff bytes"
        # The raw diff text is intentionally NOT stored on the model: only a
        # reference handle, a short summary, and a size are retained so the diff
        # is never accidentally exported through observability (NFR-6, FM-21).
        return DiffEvidence(
            diff_handle=f"github:{path}.diff",
            summary=summary,
            truncated=False,
            byte_size=byte_size,
        )


__all__ = ["GitHubApiError", "GitHubClient", "GitHubProvider"]
