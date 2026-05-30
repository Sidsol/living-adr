"""Slice S011-04 RED tests: GitHub contents port (list/read/create), no network.

A fake GitHub client returns canned JSON / accepts PUTs so tests never touch the
network (NFR-2). Verifies provider-neutral directory listing, base64 file reads,
file creation with base64-encoded content + branch, and the mapping of GitHub
HTTP failures (404 → empty/None, 409/422 → conflict, 403 → permission).
"""

from __future__ import annotations

import base64

import pytest

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CommitConflictError,
    CommitResult,
    FileContent,
    ProviderPermissionError,
    RepositoryFile,
    SCMContentsProvider,
)
from living_adr.scm.github_provider import GitHubApiError, GitHubProvider

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="living-adr", repo_id="100"
)


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


class FakeContentsClient:
    """Fake GitHub transport: get_json from a map, put_json records calls."""

    def __init__(
        self,
        get_responses: dict[str, object] | None = None,
        errors: dict[str, GitHubApiError] | None = None,
        put_error: GitHubApiError | None = None,
    ) -> None:
        self._get = get_responses or {}
        self._errors = errors or {}
        self._put_error = put_error
        self.puts: list[tuple[str, dict]] = []

    def get_json(self, path: str) -> object:
        if path in self._errors:
            raise self._errors[path]
        if path not in self._get:
            raise GitHubApiError(404, f"not found: {path}")
        return self._get[path]

    def get_diff(self, path: str) -> str:  # pragma: no cover - unused here
        raise NotImplementedError

    def put_json(self, path: str, payload: dict) -> object:
        if self._put_error is not None:
            raise self._put_error
        self.puts.append((path, payload))
        return {
            "commit": {"sha": "commit-sha-xyz"},
            "content": {"path": payload.get("path", path), "sha": "blob-sha-xyz"},
        }


def test_github_provider_satisfies_contents_port() -> None:
    provider = GitHubProvider(FakeContentsClient())
    assert isinstance(provider, SCMContentsProvider)


def test_list_directory_returns_repository_files() -> None:
    listing = [
        {
            "name": "0001-adopt.md",
            "path": "docs/adr/0001-adopt.md",
            "sha": "s1",
            "type": "file",
        },
        {
            "name": "0002-use.md",
            "path": "docs/adr/0002-use.md",
            "sha": "s2",
            "type": "file",
        },
    ]
    client = FakeContentsClient(
        {"/repos/acme/living-adr/contents/docs/adr?ref=main": listing}
    )
    provider = GitHubProvider(client)
    files = provider.list_directory(REPO, "main", "docs/adr")
    assert all(isinstance(f, RepositoryFile) for f in files)
    assert [f.name for f in files] == ["0001-adopt.md", "0002-use.md"]
    assert files[0].path == "docs/adr/0001-adopt.md"


def test_list_directory_missing_directory_is_empty() -> None:
    provider = GitHubProvider(FakeContentsClient())  # 404 for any path
    assert provider.list_directory(REPO, "main", "docs/adr") == ()


def test_read_file_decodes_base64_content() -> None:
    body = "# ADR\n\n<!-- livingadr_decision_id: d-1 -->\n"
    client = FakeContentsClient(
        {
            "/repos/acme/living-adr/contents/docs/adr/0001-adopt.md?ref=main": {
                "path": "docs/adr/0001-adopt.md",
                "sha": "blob1",
                "encoding": "base64",
                "content": _b64(body),
            }
        }
    )
    provider = GitHubProvider(client)
    content = provider.read_file(REPO, "main", "docs/adr/0001-adopt.md")
    assert isinstance(content, FileContent)
    assert content.text == body
    assert content.sha == "blob1"


def test_read_missing_file_returns_none() -> None:
    provider = GitHubProvider(FakeContentsClient())
    assert provider.read_file(REPO, "main", "docs/adr/0001-adopt.md") is None


def test_create_file_puts_base64_content_and_returns_commit() -> None:
    client = FakeContentsClient()
    provider = GitHubProvider(client)
    result = provider.create_file(
        REPO,
        "main",
        "docs/adr/0001-adopt.md",
        "# ADR body\n",
        "docs(adr): publish 0001-adopt",
    )
    assert isinstance(result, CommitResult)
    assert result.commit_sha == "commit-sha-xyz"
    assert result.path == "docs/adr/0001-adopt.md"
    assert result.created is True
    # The PUT carried base64 content + branch (no raw body leakage on the wire).
    path, payload = client.puts[0]
    assert path == "/repos/acme/living-adr/contents/docs/adr/0001-adopt.md"
    assert payload["branch"] == "main"
    assert base64.b64decode(payload["content"]).decode("utf-8") == "# ADR body\n"


def test_create_file_conflict_maps_to_commit_conflict_error() -> None:
    provider = GitHubProvider(FakeContentsClient(put_error=GitHubApiError(409)))
    with pytest.raises(CommitConflictError):
        provider.create_file(REPO, "main", "docs/adr/0001-x.md", "body", "msg")


def test_create_file_sha_mismatch_422_maps_to_commit_conflict_error() -> None:
    provider = GitHubProvider(FakeContentsClient(put_error=GitHubApiError(422)))
    with pytest.raises(CommitConflictError):
        provider.create_file(REPO, "main", "docs/adr/0001-x.md", "body", "msg")


def test_create_file_permission_denied_maps_to_provider_permission_error() -> None:
    provider = GitHubProvider(FakeContentsClient(put_error=GitHubApiError(403)))
    with pytest.raises(ProviderPermissionError):
        provider.create_file(REPO, "main", "docs/adr/0001-x.md", "body", "msg")
