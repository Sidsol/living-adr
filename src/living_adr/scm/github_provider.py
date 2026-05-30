"""GitHub provider adapter behind the SCMProvider port (feature 003, slice 4).

Implements minimal merged-PR evidence fetches (PR metadata, changed files, diff)
through an injected, fakeable :class:`GitHubClient` seam so tests never touch the
network (NFR-4). GitHub REST/permission details live here; workflow code depends
only on the provider-neutral :class:`~living_adr.core.scm.SCMProvider` port.

Minimal-access discipline (NFR-3, FM-18): only the PR, its changed-file list, and
its diff are fetched. No broad history, commit, or contents mining.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from typing import Protocol

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    ChangedFileMetadata,
    CommitConflictError,
    CommitResult,
    DiffEvidence,
    FileContent,
    InstallationStatus,
    InstallationVerification,
    ProviderPermissionError,
    PullRequestMetadata,
    RateLimitError,
    RepositoryFile,
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

    def put_json(self, path: str, payload: dict) -> object: ...


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

    @staticmethod
    def _installation_path(repository: RepositoryIdentity) -> str:
        return f"/repos/{repository.owner}/{repository.repo}/installation"

    @staticmethod
    def _repo_path(repository: RepositoryIdentity) -> str:
        return f"/repos/{repository.owner}/{repository.repo}"

    def verify_installation(
        self, repository: RepositoryIdentity, installation_id: str
    ) -> InstallationVerification:
        """Verify the GitHub App installation for ``repository`` (feature 014).

        Returns a safe :class:`InstallationVerification` (no tokens/keys). All
        GitHub HTTP details are mapped to provider-neutral statuses here so
        onboarding diagnostics never see raw API codes (FM-24). Only the
        installation endpoint plus a single repo-metadata read are called — no
        broad history/contents mining (FM-18).
        """

        key = repository.key
        try:
            raw = self._client.get_json(self._installation_path(repository))
        except GitHubApiError as exc:
            return InstallationVerification(
                repository_key=key,
                expected_installation_id=installation_id,
                status=self._status_for_api_error(exc),
            )

        if not isinstance(raw, Mapping):
            return InstallationVerification(
                repository_key=key,
                expected_installation_id=installation_id,
                status=InstallationStatus.ERROR,
            )

        actual_id = raw.get("id")
        actual_id_str = str(actual_id) if actual_id is not None else None
        permissions = self._coerce_permissions(raw.get("permissions"))
        suspended = raw.get("suspended_at") is not None

        if suspended:
            status = InstallationStatus.SUSPENDED
        elif actual_id_str is None:
            status = InstallationStatus.ERROR
        elif actual_id_str != installation_id:
            status = InstallationStatus.MISMATCHED
        else:
            status = InstallationStatus.INSTALLED

        repo_id: str | None = None
        default_branch: str | None = None
        if status is InstallationStatus.INSTALLED:
            repo_id, default_branch = self._fetch_repo_metadata(repository)

        return InstallationVerification(
            repository_key=key,
            expected_installation_id=installation_id,
            installation_id=actual_id_str,
            repo_id=repo_id,
            default_branch=default_branch,
            permissions=permissions,
            status=status,
        )

    @staticmethod
    def _status_for_api_error(error: GitHubApiError) -> InstallationStatus:
        if error.status == 404:
            return InstallationStatus.NOT_INSTALLED
        if error.status == 429 or (error.status == 403 and error.rate_limited):
            return InstallationStatus.RATE_LIMITED
        if error.status == 403:
            return InstallationStatus.ACCESS_DENIED
        return InstallationStatus.ERROR

    @staticmethod
    def _coerce_permissions(value: object) -> dict[str, str]:
        if not isinstance(value, Mapping):
            return {}
        return {str(k): str(v) for k, v in value.items()}

    def _fetch_repo_metadata(
        self, repository: RepositoryIdentity
    ) -> tuple[str | None, str | None]:
        try:
            data = self._client.get_json(self._repo_path(repository))
        except GitHubApiError:
            return None, None
        if not isinstance(data, Mapping):
            return None, None
        repo_id = data.get("id")
        default_branch = data.get("default_branch")
        return (
            str(repo_id) if repo_id is not None else None,
            str(default_branch) if default_branch is not None else None,
        )


    # --- Contents port (feature 011 publish-back) -----------------------

    def _contents_path(
        self, repository: RepositoryIdentity, path: str
    ) -> str:
        return f"/repos/{repository.owner}/{repository.repo}/contents/{path}"

    def list_directory(
        self, repository: RepositoryIdentity, branch: str, directory: str
    ) -> tuple[RepositoryFile, ...]:
        url = f"{self._contents_path(repository, directory)}?ref={branch}"
        try:
            data = self._client.get_json(url)
        except GitHubApiError as exc:
            if exc.status == 404:
                # Directory does not exist yet → treat as empty (first ADR).
                return ()
            raise _map_api_error(exc) from exc
        if not isinstance(data, Sequence):
            raise TransientProviderError("unexpected directory payload shape")
        files: list[RepositoryFile] = []
        for entry in data:
            if not isinstance(entry, Mapping):
                continue
            files.append(
                RepositoryFile(
                    name=str(entry.get("name") or ""),
                    path=str(entry.get("path") or ""),
                    sha=entry.get("sha"),
                    type=str(entry.get("type") or "file"),
                )
            )
        return tuple(files)

    def read_file(
        self, repository: RepositoryIdentity, branch: str, path: str
    ) -> FileContent | None:
        url = f"{self._contents_path(repository, path)}?ref={branch}"
        try:
            data = self._client.get_json(url)
        except GitHubApiError as exc:
            if exc.status == 404:
                return None
            raise _map_api_error(exc) from exc
        if not isinstance(data, Mapping):
            raise TransientProviderError("unexpected file payload shape")
        raw = data.get("content")
        encoding = str(data.get("encoding") or "base64")
        if not isinstance(raw, str):
            text = ""
        elif encoding == "base64":
            text = base64.b64decode(raw).decode("utf-8")
        else:
            text = raw
        return FileContent(
            path=str(data.get("path") or path),
            text=text,
            sha=data.get("sha"),
        )

    def create_file(
        self,
        repository: RepositoryIdentity,
        branch: str,
        path: str,
        content: str,
        message: str,
        *,
        sha: str | None = None,
    ) -> CommitResult:
        payload: dict = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
            "path": path,
        }
        if sha is not None:
            payload["sha"] = sha
        try:
            data = self._client.put_json(self._contents_path(repository, path), payload)
        except GitHubApiError as exc:
            if exc.status in (409, 422):
                raise CommitConflictError(str(exc)) from exc
            raise _map_api_error(exc) from exc
        if not isinstance(data, Mapping):
            raise TransientProviderError("unexpected commit payload shape")
        commit = data.get("commit") if isinstance(data.get("commit"), Mapping) else {}
        content_obj = (
            data.get("content") if isinstance(data.get("content"), Mapping) else {}
        )
        return CommitResult(
            commit_sha=str(commit.get("sha") or ""),
            path=str(content_obj.get("path") or path),
            content_sha=content_obj.get("sha"),
            created=sha is None,
        )


__all__ = ["GitHubApiError", "GitHubClient", "GitHubProvider"]
