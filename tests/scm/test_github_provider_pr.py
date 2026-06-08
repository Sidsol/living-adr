"""Tests: GitHubProvider branch + pull-request primitives (feature 011 PR publish).

Uses a fake GitHub client (no network): head-SHA lookup, idempotent branch
creation (422 = already exists), and opening a pull request.
"""

from __future__ import annotations

from living_adr.core.repository import RepositoryIdentity
from living_adr.scm.github_provider import (
    GitHubApiError,
    GitHubProvider,
    PullRequestHandle,
)

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


class _FakeClient:
    def __init__(self, *, get=None, post=None, post_errors=None) -> None:
        self._get = get or {}
        self._post = post or {}
        self._post_errors = post_errors or {}
        self.posts: list[tuple[str, dict]] = []

    def get_json(self, path: str) -> object:
        if path in self._get:
            return self._get[path]
        raise GitHubApiError(404, "not found")

    def get_diff(self, path: str) -> str:  # pragma: no cover - unused here
        raise NotImplementedError

    def put_json(self, path: str, payload: dict) -> object:  # pragma: no cover
        raise NotImplementedError

    def post_json(self, path: str, payload: dict) -> object:
        self.posts.append((path, payload))
        if path in self._post_errors:
            raise self._post_errors[path]
        return self._post.get(path, {})


def test_get_branch_head_sha() -> None:
    client = _FakeClient(
        get={"/repos/acme/widgets/git/ref/heads/master": {"object": {"sha": "abc123"}}}
    )
    assert GitHubProvider(client).get_branch_head_sha(REPO, "master") == "abc123"


def test_create_branch_success_sends_ref_payload() -> None:
    client = _FakeClient(post={"/repos/acme/widgets/git/refs": {"ref": "x"}})
    created = GitHubProvider(client).create_branch(REPO, "livingadr/x", "abc123")

    assert created is True
    path, payload = client.posts[-1]
    assert path == "/repos/acme/widgets/git/refs"
    assert payload == {"ref": "refs/heads/livingadr/x", "sha": "abc123"}


def test_create_branch_existing_is_idempotent() -> None:
    client = _FakeClient(
        post_errors={"/repos/acme/widgets/git/refs": GitHubApiError(422, "exists")}
    )
    assert GitHubProvider(client).create_branch(REPO, "livingadr/x", "abc") is False


def test_open_pull_request_returns_handle() -> None:
    client = _FakeClient(
        post={
            "/repos/acme/widgets/pulls": {
                "number": 7,
                "html_url": "https://github.com/acme/widgets/pull/7",
            }
        }
    )

    pr = GitHubProvider(client).open_pull_request(
        REPO, title="Add ADR", head="livingadr/x", base="master", body="b"
    )

    assert isinstance(pr, PullRequestHandle)
    assert pr.number == 7
    assert "pull/7" in pr.html_url
    path, payload = client.posts[-1]
    assert path == "/repos/acme/widgets/pulls"
    assert payload == {
        "title": "Add ADR",
        "head": "livingadr/x",
        "base": "master",
        "body": "b",
    }
