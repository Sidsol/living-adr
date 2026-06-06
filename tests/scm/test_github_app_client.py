"""RED tests: real GitHub App transport behind the GitHubClient seam.

Drives the GitHub App authentication flow through an in-memory
``httpx.MockTransport`` so no network call ever occurs (NFR-4): App JWT minting,
installation-token exchange with caching + refresh, the authenticated
``get_json``/``get_diff``/``put_json`` verbs, and mapping of non-2xx responses
into :class:`GitHubApiError`. A final test wraps the client in
:class:`GitHubProvider` to prove it satisfies the seam end to end.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import SCMFetchHandle
from living_adr.scm.github_app_client import GitHubAppClient, build_app_jwt
from living_adr.scm.github_provider import GitHubApiError, GitHubProvider

APP_ID = "123456"
INSTALLATION_ID = "987654"
INSTALL_TOKEN = "ghs_installationtoken"  # noqa: S105 - test fixture, not a secret

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)
HANDLE = SCMFetchHandle(
    installation_id=INSTALLATION_ID,
    pr_number=42,
    head_sha="headsha",
    base_ref="main",
    merge_commit_sha="mergesha",
)
_PR_JSON = {
    "number": 42,
    "title": "Add httpx client",
    "state": "closed",
    "merged": True,
    "user": {"login": "octocat"},
    "head": {"ref": "feature/httpx"},
    "base": {"ref": "main"},
    "merge_commit_sha": "mergesha",
}


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[str, str]:
    """A throwaway RSA keypair (PEM strings) for signing/verifying App JWTs."""

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    return private_pem, public_pem


class FakeGitHub:
    """In-memory GitHub API: mints installation tokens and serves canned routes.

    The handler verifies that the access-token request is authorised with a
    valid RS256 App JWT, and that every data request uses the *installation*
    token (never the App JWT). Routes are registered with :meth:`add`.
    """

    def __init__(self, public_pem: str, clock: Callable[[], datetime]) -> None:
        self._public_pem = public_pem
        self._clock = clock
        self.token_requests: list[httpx.Request] = []
        self.data_requests: list[httpx.Request] = []
        self._routes: dict[tuple[str, str], tuple] = {}

    def add(
        self,
        method: str,
        path: str,
        *,
        status: int = 200,
        json_body: object | None = None,
        text_body: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._routes[(method, path)] = (status, json_body, text_body, headers or {})

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith("/access_tokens"):
            self.token_requests.append(request)
            auth = request.headers.get("Authorization", "")
            assert auth.startswith("Bearer ")
            claims = jwt.decode(
                auth[7:],
                self._public_pem,
                algorithms=["RS256"],
                options={"verify_exp": False},
            )
            assert claims["iss"] == APP_ID
            expires = self._clock() + timedelta(hours=1)
            return httpx.Response(
                201,
                json={"token": INSTALL_TOKEN, "expires_at": expires.isoformat()},
            )

        self.data_requests.append(request)
        assert request.headers.get("Authorization") == f"Bearer {INSTALL_TOKEN}"
        route = self._routes.get((request.method, path))
        if route is None:
            return httpx.Response(404, json={"message": "no such route"})
        status, json_body, text_body, headers = route
        if text_body is not None:
            return httpx.Response(status, text=text_body, headers=headers)
        return httpx.Response(status, json=json_body, headers=headers)


def _make_client(
    fake: FakeGitHub, private_pem: str, now: Callable[[], datetime]
) -> GitHubAppClient:
    http = httpx.Client(
        transport=httpx.MockTransport(fake.handler),
        base_url="https://api.github.com",
    )
    return GitHubAppClient(
        app_id=APP_ID,
        private_key_pem=private_pem,
        installation_id=INSTALLATION_ID,
        http_client=http,
        now=now,
    )


def test_get_json_uses_installation_token_and_returns_payload(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    now = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    fake.add("GET", "/repos/acme/widgets/pulls/42", json_body=_PR_JSON)
    client = _make_client(fake, private_pem, now)

    assert client.get_json("/repos/acme/widgets/pulls/42") == _PR_JSON
    assert len(fake.token_requests) == 1
    assert fake.data_requests[-1].headers["Accept"] == "application/vnd.github+json"


def test_installation_token_is_cached_across_calls(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    now = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    fake.add("GET", "/repos/acme/widgets/pulls/42", json_body=_PR_JSON)
    fake.add("GET", "/repos/acme/widgets", json_body={"id": 1})
    client = _make_client(fake, private_pem, now)

    client.get_json("/repos/acme/widgets/pulls/42")
    client.get_json("/repos/acme/widgets")

    assert len(fake.token_requests) == 1


def test_token_refreshes_after_expiry(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    clock = {"now": datetime(2026, 1, 1, tzinfo=UTC)}
    now = lambda: clock["now"]  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    fake.add("GET", "/repos/acme/widgets", json_body={"id": 1})
    client = _make_client(fake, private_pem, now)

    client.get_json("/repos/acme/widgets")
    clock["now"] = clock["now"] + timedelta(hours=1, minutes=1)
    client.get_json("/repos/acme/widgets")

    assert len(fake.token_requests) == 2


def test_get_diff_requests_diff_media_type_and_returns_text(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    now = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    diff = "diff --git a/x b/x\n+added\n"
    fake.add("GET", "/repos/acme/widgets/pulls/42", text_body=diff)
    client = _make_client(fake, private_pem, now)

    assert client.get_diff("/repos/acme/widgets/pulls/42") == diff
    assert (
        fake.data_requests[-1].headers["Accept"]
        == "application/vnd.github.v3.diff"
    )


def test_put_json_sends_body_and_returns_response(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    now = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    fake.add(
        "PUT",
        "/repos/acme/widgets/contents/docs/adr/0001.md",
        json_body={"commit": {"sha": "abc"}},
    )
    client = _make_client(fake, private_pem, now)

    result = client.put_json(
        "/repos/acme/widgets/contents/docs/adr/0001.md",
        {"message": "add adr", "content": "Zm9v"},
    )

    assert result == {"commit": {"sha": "abc"}}
    sent = json.loads(fake.data_requests[-1].content)
    assert sent["message"] == "add adr"


def test_post_json_sends_body_and_returns_response(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    now = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    fake.add("POST", "/repos/acme/widgets/pulls", json_body={"number": 7})
    client = _make_client(fake, private_pem, now)

    result = client.post_json("/repos/acme/widgets/pulls", {"title": "Add ADR"})

    assert result == {"number": 7}
    sent = json.loads(fake.data_requests[-1].content)
    assert sent["title"] == "Add ADR"


def test_http_404_maps_to_github_api_error(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    now = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    client = _make_client(fake, private_pem, now)

    with pytest.raises(GitHubApiError) as excinfo:
        client.get_json("/repos/acme/widgets/pulls/404")

    assert excinfo.value.status == 404
    assert excinfo.value.rate_limited is False


def test_rate_limited_403_sets_flag(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    now = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    fake.add(
        "GET",
        "/repos/acme/widgets/pulls/42",
        status=403,
        json_body={"message": "rate limit exceeded"},
        headers={"X-RateLimit-Remaining": "0"},
    )
    client = _make_client(fake, private_pem, now)

    with pytest.raises(GitHubApiError) as excinfo:
        client.get_json("/repos/acme/widgets/pulls/42")

    assert excinfo.value.status == 403
    assert excinfo.value.rate_limited is True


def test_http_429_sets_rate_limited(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    now = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    fake.add(
        "GET",
        "/repos/acme/widgets/pulls/42",
        status=429,
        json_body={"message": "too many requests"},
    )
    client = _make_client(fake, private_pem, now)

    with pytest.raises(GitHubApiError) as excinfo:
        client.get_json("/repos/acme/widgets/pulls/42")

    assert excinfo.value.status == 429
    assert excinfo.value.rate_limited is True


def test_build_app_jwt_is_rs256_with_issuer(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    issued = datetime(2026, 1, 1, tzinfo=UTC)

    token = build_app_jwt(APP_ID, private_pem, issued)

    assert jwt.get_unverified_header(token)["alg"] == "RS256"
    claims = jwt.decode(
        token, public_pem, algorithms=["RS256"], options={"verify_exp": False}
    )
    assert claims["iss"] == APP_ID
    assert claims["exp"] > claims["iat"]


def test_satisfies_githubclient_seam_via_provider(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    now = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
    fake = FakeGitHub(public_pem, now)
    fake.add("GET", "/repos/acme/widgets/pulls/42", json_body=_PR_JSON)
    provider = GitHubProvider(_make_client(fake, private_pem, now))

    pr = provider.fetch_pull_request(REPO, HANDLE)

    assert pr.number == 42
    assert pr.merged is True
