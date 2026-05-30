"""Slice 3 RED tests: GitHubProvider.verify_installation (fakeable, no network).

Verifies GitHub App installation status through the feature 003 provider seam
using a canned client, covering installed/not-installed/suspended/mismatched/
access-denied/rate-limited branches. No live GitHub call is made.
"""

from __future__ import annotations

import pytest

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import InstallationStatus, InstallationVerification
from living_adr.scm.github_provider import GitHubApiError, GitHubProvider

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)
_INSTALL_PATH = "/installation"
_REPO_PATH = "/repos/acme/widgets"


class FakeGitHubClient:
    """Canned GitHub client keyed by path suffix; never touches the network."""

    def __init__(self, *, json_map=None, error=None) -> None:
        self._json_map = json_map or {}
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

    def get_diff(self, path: str) -> str:  # pragma: no cover - unused here
        raise AssertionError("diff not expected")


def _provider(*, install_payload=None, repo_payload=None, error=None):
    json_map = {}
    if install_payload is not None:
        json_map[_INSTALL_PATH] = install_payload
    if repo_payload is not None:
        json_map[_REPO_PATH] = repo_payload
    return GitHubProvider(FakeGitHubClient(json_map=json_map, error=error))


def test_installed_with_read_permissions() -> None:
    provider = _provider(
        install_payload={
            "id": "inst-555",
            "permissions": {"contents": "read", "metadata": "read"},
            "suspended_at": None,
        },
        repo_payload={"id": "100", "default_branch": "main"},
    )
    result = provider.verify_installation(REPO, "inst-555")
    assert isinstance(result, InstallationVerification)
    assert result.status is InstallationStatus.INSTALLED
    assert result.installation_id == "inst-555"
    assert result.permissions["contents"] == "read"
    assert result.repo_id == "100"
    assert result.default_branch == "main"
    assert result.repository_key == "github.com/acme/widgets"


def test_installed_with_write_permissions() -> None:
    provider = _provider(
        install_payload={
            "id": "inst-555",
            "permissions": {"contents": "write"},
            "suspended_at": None,
        },
        repo_payload={"id": "100", "default_branch": "main"},
    )
    result = provider.verify_installation(REPO, "inst-555")
    assert result.status is InstallationStatus.INSTALLED
    assert result.permissions["contents"] == "write"


def test_not_installed_maps_404() -> None:
    provider = _provider(error=GitHubApiError(404))
    result = provider.verify_installation(REPO, "inst-555")
    assert result.status is InstallationStatus.NOT_INSTALLED
    assert result.installation_id is None


def test_suspended_installation() -> None:
    provider = _provider(
        install_payload={
            "id": "inst-555",
            "permissions": {"contents": "read"},
            "suspended_at": "2024-01-01T00:00:00Z",
        }
    )
    result = provider.verify_installation(REPO, "inst-555")
    assert result.status is InstallationStatus.SUSPENDED


def test_mismatched_installation_id() -> None:
    provider = _provider(
        install_payload={
            "id": "inst-999",
            "permissions": {"contents": "read"},
            "suspended_at": None,
        },
        repo_payload={"id": "100", "default_branch": "main"},
    )
    result = provider.verify_installation(REPO, "inst-555")
    assert result.status is InstallationStatus.MISMATCHED
    assert result.expected_installation_id == "inst-555"
    assert result.installation_id == "inst-999"


def test_access_denied_maps_403() -> None:
    provider = _provider(error=GitHubApiError(403))
    result = provider.verify_installation(REPO, "inst-555")
    assert result.status is InstallationStatus.ACCESS_DENIED


@pytest.mark.parametrize(
    "error",
    [GitHubApiError(429), GitHubApiError(403, rate_limited=True)],
)
def test_rate_limited(error) -> None:
    provider = _provider(error=error)
    result = provider.verify_installation(REPO, "inst-555")
    assert result.status is InstallationStatus.RATE_LIMITED


def test_server_error_maps_to_error_status() -> None:
    provider = _provider(error=GitHubApiError(500))
    result = provider.verify_installation(REPO, "inst-555")
    assert result.status is InstallationStatus.ERROR


def test_only_minimal_endpoints_called_for_installed() -> None:
    provider = _provider(
        install_payload={
            "id": "inst-555",
            "permissions": {"contents": "read"},
            "suspended_at": None,
        },
        repo_payload={"id": "100", "default_branch": "main"},
    )
    provider.verify_installation(REPO, "inst-555")
    client = provider._client  # type: ignore[attr-defined]
    # Only the installation endpoint and the repo metadata endpoint; no broad
    # history/commits/contents mining (FM-18).
    assert not any("/commits" in c or "/contents" in c for c in client.calls)
