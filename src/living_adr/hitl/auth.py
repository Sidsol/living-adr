"""Local single-user UI auth + signed review nonce for feature 009.

The PoC has no multi-user identity (architecture #cross-cutting): all review
routes are guarded by one configured local UI token, and every state-changing
form POST additionally carries a signed per-review nonce bound to the thread and
the exact reviewed draft hash. This blocks CSRF-style cross-site form replay and
stops a stale nonce from approving a different draft.

Implementation note: this uses the standard library ``hmac`` only — no new
tooling and no external signing dependency. Comparisons are constant-time.
"""

from __future__ import annotations

import hashlib
import hmac


class UITokenGuard:
    """Constant-time guard for the local single-user UI token.

    When no token is configured (``token`` is ``None`` or empty) the guard is
    disabled and authorizes every request — this keeps the PoC/test harness
    usable without secrets while production deployments set ``LIVING_ADR_UI_TOKEN``.
    """

    def __init__(self, token: str | None) -> None:
        self._token = token or None

    @property
    def enabled(self) -> bool:
        return self._token is not None

    def is_authorized(self, provided: str | None) -> bool:
        if self._token is None:
            return True
        if not provided:
            return False
        return hmac.compare_digest(provided, self._token)


class NonceSigner:
    """HMAC-SHA256 signer for per-review form nonces.

    A nonce binds a ``thread_id`` to the exact ``draft_hash`` under review, so a
    submitted form can only act on the draft it was issued for. Verification is
    constant-time.
    """

    def __init__(self, secret: str) -> None:
        self._secret = (secret or "").encode("utf-8")

    def _digest(self, thread_id: str, draft_hash: str) -> str:
        message = f"{thread_id}:{draft_hash}".encode()
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    def issue(self, thread_id: str, draft_hash: str) -> str:
        return self._digest(thread_id, draft_hash)

    def verify(
        self, nonce: str | None, thread_id: str, draft_hash: str
    ) -> bool:
        if not nonce:
            return False
        expected = self._digest(thread_id, draft_hash)
        return hmac.compare_digest(nonce, expected)


__all__ = ["UITokenGuard", "NonceSigner"]
