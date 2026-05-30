"""Slice 4 RED tests: GitHubProvider behind SCMProvider (fakeable, no network).

Uses a fake GitHub client returning canned JSON/diff or raising HTTP errors, so
tests never make a real network call. Verifies minimal-fetch behavior and the
mapping of GitHub API failures into the ingestion error taxonomy.
"""

from __future__ import annotations

import pytest

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    ChangedFileMetadata,
    DiffEvidence,
    ProviderPermissionError,
    PullRequestMetadata,
    RateLimitError,
    ResourceNotFoundError,
    SCMFetchHandle,
    SCMProvider,
    TransientProviderError,
)
from living_adr.scm.github_provider import GitHubApiError, GitHubProvider

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)
HANDLE = SCMFetchHandle(
    installation_id="inst-555",
    pr_number=42,
    head_sha="headsha",
    base_ref="main",
    merge_commit_sha="mergesha",
)

_PR_JSON = {
    "number": 42,
    "title": "Add httpx client",
    "body": "Introduces outbound API client.",
    "state": "closed",
    "merged": True,
    "user": {"login": "octocat"},
    "head": {"ref": "feature/httpx"},
    "base": {"ref": "main"},
    "merge_commit_sha": "mergesha",
}
_FILES_JSON = [
    {
        "filename": "pyproject.toml",
        "status": "modified",
        "additions": 2,
        "deletions": 0,
    },
    {
        "filename": "src/app/client.py",
        "status": "added",
        "additions": 30,
        "deletions": 0,
    },
]
_DIFF_TEXT = "diff --git a/pyproject.toml b/pyproject.toml\n+httpx>=0.27\n"


class FakeGitHubClient:
    """Canned GitHub client; records paths and never touches the network."""

    def __init__(self, *, json_map=None, diff_text=_DIFF_TEXT, error=None) -> None:
        self._json_map = json_map or {}
        self._diff_text = diff_text
        self._error = error
        self.calls: list[str] = []

    def get_json(self, path: str):
        self.calls.append(path)
        if self._error is not None:
            raise self._error
        for suffix, value in self._json_map.items():
            if path.endswith(suffix):
                return value
        raise AssertionError(f"unexpected path {path}")

    def get_diff(self, path: str) -> str:
        self.calls.append(path + "#diff")
        if self._error is not None:
            raise self._error
        return self._diff_text


def _provider(**kwargs) -> GitHubProvider:
    client = FakeGitHubClient(
        json_map={"/pulls/42/files": _FILES_JSON, "/pulls/42": _PR_JSON},
        **kwargs,
    )
    return GitHubProvider(client)


def test_github_provider_satisfies_protocol() -> None:
    assert isinstance(_provider(), SCMProvider)


def test_fetch_pull_request_metadata() -> None:
    pr = _provider().fetch_pull_request(REPO, HANDLE)
    assert isinstance(pr, PullRequestMetadata)
    assert pr.number == 42
    assert pr.title == "Add httpx client"
    assert pr.author == "octocat"
    assert pr.merged is True
    assert pr.merge_commit_sha == "mergesha"


def test_fetch_changed_files() -> None:
    files = _provider().fetch_changed_files(REPO, HANDLE)
    assert all(isinstance(f, ChangedFileMetadata) for f in files)
    assert [f.filename for f in files] == ["pyproject.toml", "src/app/client.py"]
    assert files[1].status == "added"
    assert files[1].additions == 30


def test_fetch_diff_returns_handle_and_summary_not_raw_text() -> None:
    diff = _provider().fetch_diff(REPO, HANDLE)
    assert isinstance(diff, DiffEvidence)
    assert diff.diff_handle  # a reference, not the raw diff
    assert diff.byte_size == len(_DIFF_TEXT.encode())
    # The raw diff text must not be carried verbatim on the evidence model.
    serialized = diff.model_dump_json()
    assert "diff --git" not in serialized


def test_only_minimal_endpoints_are_called() -> None:
    provider = _provider()
    provider.fetch_pull_request(REPO, HANDLE)
    provider.fetch_changed_files(REPO, HANDLE)
    provider.fetch_diff(REPO, HANDLE)
    client = provider._client  # type: ignore[attr-defined]
    # No broad history/commits/contents mining — only the PR + files + diff.
    assert all("/pulls/42" in c for c in client.calls)
    assert not any("/commits" in c or "/contents" in c for c in client.calls)


@pytest.mark.parametrize(
    "error,expected",
    [
        (GitHubApiError(404), ResourceNotFoundError),
        (GitHubApiError(403, rate_limited=True), RateLimitError),
        (GitHubApiError(429), RateLimitError),
        (GitHubApiError(403), ProviderPermissionError),
        (GitHubApiError(500), TransientProviderError),
        (GitHubApiError(503), TransientProviderError),
    ],
)
def test_api_errors_map_to_provider_error_taxonomy(error, expected) -> None:
    provider = _provider(error=error)
    with pytest.raises(expected):
        provider.fetch_pull_request(REPO, HANDLE)
