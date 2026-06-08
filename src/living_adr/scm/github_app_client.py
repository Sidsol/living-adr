"""Real GitHub App transport behind the :class:`GitHubClient` seam.

Provides the production implementation the feature-003 :class:`GitHubProvider`
depends on, so the workflow service can reach the live GitHub REST API:

* mint a short-lived RS256 *App JWT* from the App ID and the ``.pem`` private key;
* exchange it for an *installation access token*, cached until shortly before its
  stated expiry and refreshed on demand;
* issue authenticated ``httpx`` calls for the ``get_json`` / ``get_diff`` /
  ``put_json`` verbs, mapping every non-2xx response into :class:`GitHubApiError`
  so the provider's error-taxonomy mapping is unchanged.

The ``httpx.Client`` transport is injectable, so tests drive the whole auth flow
through ``httpx.MockTransport`` with no network access (NFR-4). Secrets (the
private key, the App JWT, and the installation token) are never logged.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt

from living_adr.scm.github_provider import GitHubApiError

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
_JSON_ACCEPT = "application/vnd.github+json"
_DIFF_ACCEPT = "application/vnd.github.v3.diff"

# GitHub allows an App JWT lifetime of up to 10 minutes; use 9 and backdate the
# issued-at by a minute to absorb minor clock skew between us and GitHub.
_JWT_TTL = timedelta(minutes=9)
_JWT_BACKDATE = timedelta(seconds=60)

# Refresh an installation token this long before its stated expiry so an
# in-flight request never races the expiry boundary.
_TOKEN_REFRESH_SKEW = timedelta(seconds=60)
# Fallback lifetime when GitHub omits/!parses ``expires_at`` (it is normally 1h).
_DEFAULT_TOKEN_TTL = timedelta(hours=1)


def build_app_jwt(app_id: str, private_key_pem: str, now: datetime) -> str:
    """Mint an RS256 GitHub App JWT issued at ``now`` (the ``iss`` is the App ID)."""

    payload = {
        "iat": int((now - _JWT_BACKDATE).timestamp()),
        "exp": int((now + _JWT_TTL).timestamp()),
        "iss": str(app_id),
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def _parse_expiry(value: object, now: datetime) -> datetime:
    """Parse GitHub's ISO ``expires_at`` into an aware UTC datetime."""

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return now + _DEFAULT_TOKEN_TTL


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    remaining = response.headers.get("X-RateLimit-Remaining")
    return response.status_code == 403 and remaining == "0"


def _api_error_from_response(response: httpx.Response) -> GitHubApiError:
    message = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        message = str(body.get("message") or "")
    return GitHubApiError(
        response.status_code,
        message,
        rate_limited=_is_rate_limited(response),
    )


class _InstallationToken:
    """A cached installation token with its absolute expiry."""

    __slots__ = ("token", "expires_at")

    def __init__(self, token: str, expires_at: datetime) -> None:
        self.token = token
        self.expires_at = expires_at


class GitHubAppClient:
    """GitHub App-authenticated :class:`GitHubClient`.

    Structurally satisfies the :class:`~living_adr.scm.github_provider.GitHubClient`
    protocol (``get_json`` / ``get_diff`` / ``put_json``); inject it into
    :class:`~living_adr.scm.github_provider.GitHubProvider`.
    """

    def __init__(
        self,
        *,
        app_id: str,
        private_key_pem: str,
        installation_id: str,
        http_client: httpx.Client | None = None,
        base_url: str = GITHUB_API_BASE_URL,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._app_id = str(app_id)
        self._private_key_pem = private_key_pem
        self._installation_id = str(installation_id)
        self._now = now or (lambda: datetime.now(UTC))
        self._http = http_client or httpx.Client(base_url=base_url, timeout=30.0)
        self._owns_http = http_client is None
        self._token: _InstallationToken | None = None

    @classmethod
    def from_private_key_file(
        cls,
        *,
        app_id: str,
        private_key_path: str | Path,
        installation_id: str,
        http_client: httpx.Client | None = None,
        base_url: str = GITHUB_API_BASE_URL,
        now: Callable[[], datetime] | None = None,
    ) -> GitHubAppClient:
        """Build a client by reading the App's PEM private key from disk."""

        pem = Path(private_key_path).read_text(encoding="utf-8")
        return cls(
            app_id=app_id,
            private_key_pem=pem,
            installation_id=installation_id,
            http_client=http_client,
            base_url=base_url,
            now=now,
        )

    def _ensure_token(self) -> str:
        current = self._now()
        cached = self._token
        if cached is not None and cached.expires_at - _TOKEN_REFRESH_SKEW > current:
            return cached.token
        return self._refresh_token(current)

    def _refresh_token(self, current: datetime) -> str:
        app_jwt = build_app_jwt(self._app_id, self._private_key_pem, current)
        path = f"/app/installations/{self._installation_id}/access_tokens"
        response = self._http.post(
            path,
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": _JSON_ACCEPT,
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            },
        )
        if response.status_code >= 300:
            raise _api_error_from_response(response)
        data = response.json()
        token = str(data["token"])
        self._token = _InstallationToken(
            token, _parse_expiry(data.get("expires_at"), current)
        )
        return token

    def _auth_headers(self, accept: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._ensure_token()}",
            "Accept": accept,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }

    def get_json(self, path: str) -> object:
        response = self._http.get(path, headers=self._auth_headers(_JSON_ACCEPT))
        if response.status_code >= 300:
            raise _api_error_from_response(response)
        return response.json()

    def get_diff(self, path: str) -> str:
        response = self._http.get(path, headers=self._auth_headers(_DIFF_ACCEPT))
        if response.status_code >= 300:
            raise _api_error_from_response(response)
        return response.text

    def put_json(self, path: str, payload: dict) -> object:
        response = self._http.put(
            path, headers=self._auth_headers(_JSON_ACCEPT), json=payload
        )
        if response.status_code >= 300:
            raise _api_error_from_response(response)
        return response.json()

    def post_json(self, path: str, payload: dict) -> object:
        response = self._http.post(
            path, headers=self._auth_headers(_JSON_ACCEPT), json=payload
        )
        if response.status_code >= 300:
            raise _api_error_from_response(response)
        return response.json()

    def close(self) -> None:
        """Close the underlying transport if this client created it."""

        if self._owns_http:
            self._http.close()


__all__ = ["GitHubAppClient", "build_app_jwt"]
