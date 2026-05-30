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
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlparse

from living_adr.core.config import LivingADRConfig, RepositoryConfig
from living_adr.core.ingestion import IngestionErrorCategory
from living_adr.core.models import SCMEvent
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    SCMEventEnvelope,
    SCMFetchHandle,
    SCMProviderName,
    build_normalized_pr_key,
)

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


# --------------------------------------------------------------------------- #
# Slice 2: payload parsing, merged-PR filtering, repository resolution.
#
# GitHub-specific payload traversal is confined to this adapter module. Workflow
# code consumes only the provider-neutral ``GitHubPullRequestPayload`` extract and
# the resolved ``RepositoryIdentity``/``RepositoryConfig`` — never the raw dict.
# --------------------------------------------------------------------------- #

PULL_REQUEST_EVENT = "pull_request"
_DEFAULT_HOST = "github.com"


class FilterDecision(StrEnum):
    """Outcome of filtering a verified webhook payload."""

    ACCEPT = "accept"
    SKIP = "skip"
    REJECT = "reject"


@dataclass(frozen=True)
class GitHubPullRequestPayload:
    """Provider-neutral extract of the GitHub merged-PR fields we depend on.

    Provider-specific taxonomy stays here in the adapter; downstream
    normalization (slice 3) maps this into the canonical ``SCMEvent``.
    """

    pr_number: int
    pr_title: str
    pr_body: str
    merged_at: str | None
    merge_commit_sha: str | None
    head_ref: str | None
    head_sha: str | None
    base_ref: str | None
    sender: str | None
    installation_id: str | None


@dataclass(frozen=True)
class FilterResult:
    """Decision plus the data needed to persist state and normalize the event."""

    decision: FilterDecision
    error_category: IngestionErrorCategory
    payload: GitHubPullRequestPayload | None = None
    repository: RepositoryIdentity | None = None
    repo_config: RepositoryConfig | None = None
    detail: str | None = None


def _reject(category: IngestionErrorCategory, detail: str) -> FilterResult:
    return FilterResult(
        decision=FilterDecision.REJECT,
        error_category=category,
        detail=detail,
    )


def _skip(category: IngestionErrorCategory, detail: str) -> FilterResult:
    return FilterResult(
        decision=FilterDecision.SKIP,
        error_category=category,
        detail=detail,
    )


def _resolve_identity(repo_obj: Mapping[str, object]) -> RepositoryIdentity | None:
    """Build a provider-neutral identity from a GitHub ``repository`` object."""

    full_name = repo_obj.get("full_name")
    owner_obj = repo_obj.get("owner") or {}
    owner = owner_obj.get("login") if isinstance(owner_obj, Mapping) else None
    name = repo_obj.get("name")
    repo_id = repo_obj.get("id")
    html_url = repo_obj.get("html_url")

    if owner is None and isinstance(full_name, str) and "/" in full_name:
        owner, name = full_name.split("/", 1)

    host = _DEFAULT_HOST
    if isinstance(html_url, str) and html_url:
        parsed_host = urlparse(html_url).hostname
        if parsed_host:
            host = parsed_host

    if not owner or not name or repo_id is None:
        return None
    try:
        return RepositoryIdentity(
            host=host,
            owner=str(owner),
            repo=str(name),
            repo_id=str(repo_id),
        )
    except ValueError:
        return None


def parse_and_filter(
    raw_body: bytes,
    event_name: str,
    config: LivingADRConfig,
) -> FilterResult:
    """Parse a *verified* payload and decide accept/skip/reject.

    Must only be called after :func:`verify_signature` has succeeded.
    """

    if event_name != PULL_REQUEST_EVENT:
        return _skip(
            IngestionErrorCategory.NOT_PULL_REQUEST,
            f"event {event_name!r} is not a pull_request",
        )

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return _reject(IngestionErrorCategory.MALFORMED_PAYLOAD, "invalid JSON body")

    if not isinstance(payload, Mapping):
        return _reject(
            IngestionErrorCategory.MALFORMED_PAYLOAD, "payload is not an object"
        )

    pull_request = payload.get("pull_request")
    repository = payload.get("repository")
    action = payload.get("action")
    if not isinstance(pull_request, Mapping) or not isinstance(repository, Mapping):
        return _reject(
            IngestionErrorCategory.MALFORMED_PAYLOAD,
            "missing pull_request or repository object",
        )

    merged = bool(pull_request.get("merged"))
    if action != "closed" or not merged:
        return _skip(
            IngestionErrorCategory.NOT_MERGED,
            f"action={action!r} merged={merged} is not a merged PR",
        )

    identity = _resolve_identity(repository)
    if identity is None:
        return _reject(
            IngestionErrorCategory.MALFORMED_PAYLOAD,
            "could not resolve repository identity",
        )

    repo_config = config.get(identity.key)
    if repo_config is None:
        return FilterResult(
            decision=FilterDecision.REJECT,
            error_category=IngestionErrorCategory.UNCONFIGURED_REPOSITORY,
            repository=identity,
            detail=f"repository {identity.key} is not configured",
        )

    head = pull_request.get("head") or {}
    base = pull_request.get("base") or {}
    sender_obj = payload.get("sender") or {}
    installation_obj = payload.get("installation") or {}
    # Config is the source of truth for the installation id used to authenticate;
    # fall back to the payload-declared installation only if config omits it.
    installation_id = (
        repo_config.github_app_installation_id
        or (
            str(installation_obj.get("id"))
            if isinstance(installation_obj, Mapping)
            and installation_obj.get("id") is not None
            else None
        )
    )

    extracted = GitHubPullRequestPayload(
        pr_number=int(pull_request.get("number")),
        pr_title=str(pull_request.get("title") or ""),
        pr_body=str(pull_request.get("body") or ""),
        merged_at=pull_request.get("merged_at"),
        merge_commit_sha=pull_request.get("merge_commit_sha"),
        head_ref=head.get("ref") if isinstance(head, Mapping) else None,
        head_sha=head.get("sha") if isinstance(head, Mapping) else None,
        base_ref=base.get("ref") if isinstance(base, Mapping) else None,
        sender=(
            sender_obj.get("login") if isinstance(sender_obj, Mapping) else None
        ),
        installation_id=installation_id,
    )
    return FilterResult(
        decision=FilterDecision.ACCEPT,
        error_category=IngestionErrorCategory.NONE,
        payload=extracted,
        repository=identity,
        repo_config=repo_config,
    )


# --------------------------------------------------------------------------- #
# Slice 3: normalize an accepted GitHub payload into the canonical SCMEvent.
#
# The canonical SCMEvent (feature 001) is emitted unchanged; richer normalized
# context (normalized PR key, provider-neutral fetch handle, opaque provider
# metadata) is carried by the wrapping SCMEventEnvelope. Changed files / diff are
# evidence and are fetched later (slice 4), so they are intentionally absent here.
# --------------------------------------------------------------------------- #


def _parse_merged_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_to_scm_event(
    delivery_id: str,
    repository: RepositoryIdentity,
    payload: GitHubPullRequestPayload,
) -> SCMEventEnvelope:
    """Map an accepted, filtered GitHub merged-PR into a canonical event envelope."""

    event = SCMEvent(
        repository=repository,
        delivery_id=delivery_id,
        provider=SCMProviderName.GITHUB.value,
        event_type="merged_pr",
        pr_number=payload.pr_number,
        pr_title=payload.pr_title,
        merged_at=_parse_merged_at(payload.merged_at),
        diff_summary="",
        changed_files=(),
    )
    normalized_pr_key = build_normalized_pr_key(
        SCMProviderName.GITHUB,
        repository,
        payload.pr_number,
        payload.merge_commit_sha,
    )
    fetch_handle = SCMFetchHandle(
        installation_id=payload.installation_id or "",
        pr_number=payload.pr_number,
        head_sha=payload.head_sha,
        head_ref=payload.head_ref,
        base_ref=payload.base_ref,
        merge_commit_sha=payload.merge_commit_sha,
    )
    return SCMEventEnvelope(
        event=event,
        provider=SCMProviderName.GITHUB,
        provider_event_type="pull_request.closed",
        normalized_pr_key=normalized_pr_key,
        fetch_handle=fetch_handle,
        sender=payload.sender,
        provider_metadata={},
    )
