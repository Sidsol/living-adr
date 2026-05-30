"""GitHub webhook adapter: raw-body HMAC verification and header extraction.

This module is the GitHub trust boundary (feature 003, slice 1+). It operates on
the *raw* request bytes so signature verification never depends on a parsed or
re-serialized body. JSON parsing, repository filtering, and normalization (added
in later slices) only run *after* :func:`verify_signature` succeeds.

Security contract (architecture #cross-cutting, FM-14, NFR-1):
- ``X-Hub-Signature-256`` is verified over raw bytes with a constant-time compare.
- Only the ``sha256=`` algorithm is accepted; ``sha1=`` and others are rejected.
- Required headers (delivery id, event name) are enforced before processing.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass

SIGNATURE_HEADER = "X-Hub-Signature-256"
DELIVERY_HEADER = "X-GitHub-Delivery"
EVENT_HEADER = "X-GitHub-Event"

_SIGNATURE_PREFIX = "sha256="


class WebhookError(Exception):
    """Base class for webhook verification/parsing failures."""


class MissingHeaderError(WebhookError):
    """A required webhook header (delivery id or event name) is absent."""


class InvalidSignatureError(WebhookError):
    """The request signature is missing, malformed, or does not match."""


@dataclass(frozen=True)
class WebhookHeaders:
    """Typed view over the GitHub webhook headers we depend on."""

    delivery_id: str
    event_name: str
    signature: str | None


def compute_signature(secret: str, raw_body: bytes) -> str:
    """Compute the GitHub ``sha256=<hexdigest>`` signature for raw bytes."""

    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"{_SIGNATURE_PREFIX}{digest}"


def verify_signature(
    secret: str, raw_body: bytes, signature_header: str | None
) -> bool:
    """Constant-time verify ``signature_header`` against raw ``raw_body``.

    Returns ``False`` (never raises) for missing, malformed, wrong-algorithm, or
    mismatching signatures so callers can reject uniformly before any side effect.
    """

    if not signature_header or not signature_header.startswith(_SIGNATURE_PREFIX):
        return False
    expected = compute_signature(secret, raw_body)
    return hmac.compare_digest(expected, signature_header)


def _lookup(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup (HTTP header names are case-insensitive)."""

    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def extract_headers(headers: Mapping[str, str]) -> WebhookHeaders:
    """Extract required webhook headers, raising on missing delivery id/event."""

    delivery_id = _lookup(headers, DELIVERY_HEADER)
    if not delivery_id:
        raise MissingHeaderError(f"missing required header: {DELIVERY_HEADER}")
    event_name = _lookup(headers, EVENT_HEADER)
    if not event_name:
        raise MissingHeaderError(f"missing required header: {EVENT_HEADER}")
    signature = _lookup(headers, SIGNATURE_HEADER)
    return WebhookHeaders(
        delivery_id=delivery_id,
        event_name=event_name,
        signature=signature,
    )
