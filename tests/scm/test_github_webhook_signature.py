"""Slice 1 RED tests: GitHub webhook raw-body HMAC verification.

These tests pin the security boundary: signatures are verified over the *raw*
request bytes before any JSON parsing or side effects, and required headers
(delivery id, event name) are enforced. No network access is involved.
"""

from __future__ import annotations

import hashlib
import hmac

import pytest

from living_adr.scm.github_webhook import (
    DELIVERY_HEADER,
    EVENT_HEADER,
    SIGNATURE_HEADER,
    MissingHeaderError,
    WebhookHeaders,
    compute_signature,
    extract_headers,
    verify_signature,
)

SECRET = "s3cr3t-webhook-key"
RAW_BODY = b'{"action":"closed","number":42}'


def _sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_compute_signature_matches_github_format() -> None:
    assert compute_signature(SECRET, RAW_BODY) == _sign(SECRET, RAW_BODY)
    assert compute_signature(SECRET, RAW_BODY).startswith("sha256=")


def test_valid_signature_over_raw_bytes_succeeds() -> None:
    signature = _sign(SECRET, RAW_BODY)
    assert verify_signature(SECRET, RAW_BODY, signature) is True


def test_body_tampering_fails_verification() -> None:
    signature = _sign(SECRET, RAW_BODY)
    tampered = RAW_BODY + b" "  # whitespace change must invalidate
    assert verify_signature(SECRET, tampered, signature) is False


def test_wrong_secret_fails_verification() -> None:
    signature = _sign("other-secret", RAW_BODY)
    assert verify_signature(SECRET, RAW_BODY, signature) is False


def test_missing_signature_header_fails() -> None:
    assert verify_signature(SECRET, RAW_BODY, None) is False
    assert verify_signature(SECRET, RAW_BODY, "") is False


def test_unsupported_algorithm_prefix_fails() -> None:
    sha1 = hmac.new(SECRET.encode(), RAW_BODY, hashlib.sha1).hexdigest()
    assert verify_signature(SECRET, RAW_BODY, f"sha1={sha1}") is False


def test_malformed_signature_value_fails() -> None:
    assert verify_signature(SECRET, RAW_BODY, "sha256=not-hex-zzzz") is False
    assert verify_signature(SECRET, RAW_BODY, "garbage") is False


def test_extract_headers_returns_typed_values() -> None:
    headers = {
        SIGNATURE_HEADER: _sign(SECRET, RAW_BODY),
        DELIVERY_HEADER: "delivery-123",
        EVENT_HEADER: "pull_request",
    }
    extracted = extract_headers(headers)
    assert isinstance(extracted, WebhookHeaders)
    assert extracted.delivery_id == "delivery-123"
    assert extracted.event_name == "pull_request"
    assert extracted.signature == _sign(SECRET, RAW_BODY)


def test_extract_headers_is_case_insensitive() -> None:
    headers = {
        "x-hub-signature-256": "sha256=abc",
        "x-github-delivery": "delivery-456",
        "x-github-event": "pull_request",
    }
    extracted = extract_headers(headers)
    assert extracted.delivery_id == "delivery-456"
    assert extracted.event_name == "pull_request"


def test_missing_delivery_id_raises() -> None:
    headers = {SIGNATURE_HEADER: "sha256=abc", EVENT_HEADER: "pull_request"}
    with pytest.raises(MissingHeaderError):
        extract_headers(headers)


def test_missing_event_name_raises() -> None:
    headers = {SIGNATURE_HEADER: "sha256=abc", DELIVERY_HEADER: "delivery-1"}
    with pytest.raises(MissingHeaderError):
        extract_headers(headers)
