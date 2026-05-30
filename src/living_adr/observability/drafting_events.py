"""Metadata-only drafting telemetry (feature 008, slice S-007, US-7).

Builds observability metadata for the Claude ADR drafting node that satisfies
the architecture default-deny raw-export contract (#cross-cutting, FM-21,
NFR-4): only identifiers, model id, token counts, policy state, result type,
error class, content hash, and citation count are emitted. Raw prompts, diffs,
Claude responses, draft bodies, and secrets are never included.

These helpers return plain metadata mappings so they can be unit-tested in
isolation and then handed to any
:class:`~living_adr.core.observability.Observability` implementation by the
drafting node.
"""

from __future__ import annotations

DRAFTING_STARTED = "adr_drafting.started"
DRAFTING_POLICY_BLOCKED = "adr_drafting.policy_blocked"
DRAFTING_BUDGET_BLOCKED = "adr_drafting.budget_blocked"
DRAFTING_PROVIDER_ERROR = "adr_drafting.provider_error"
DRAFTING_INVALID_OUTPUT = "adr_drafting.invalid_output"
DRAFTING_SUCCEEDED = "adr_drafting.succeeded"
DRAFTING_COMPLETED = "adr_drafting.completed"

#: Closed allowlist of metadata keys any drafting event may carry. Anything
#: outside this set is, by construction, a potential raw-payload leak.
ALLOWED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "repository_key",
        "normalized_event_key",
        "structural_change_id",
        "model_id",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "policy_allowed",
        "reason",
        "result_type",
        "error_class",
        "content_hash",
        "citation_count",
    }
)


def _base(
    repository_key: str,
    structural_change_id: str,
    normalized_event_key: str | None = None,
) -> dict[str, object]:
    meta: dict[str, object] = {
        "repository_key": repository_key,
        "structural_change_id": structural_change_id,
    }
    if normalized_event_key is not None:
        meta["normalized_event_key"] = normalized_event_key
    return meta


def started_metadata(
    *,
    repository_key: str,
    structural_change_id: str,
    model_id: str,
    normalized_event_key: str | None = None,
) -> dict[str, object]:
    """Safe metadata for a drafting-started event."""

    meta = _base(repository_key, structural_change_id, normalized_event_key)
    meta["model_id"] = model_id
    return meta


def policy_blocked_metadata(
    *,
    repository_key: str,
    structural_change_id: str,
    reason: str,
    normalized_event_key: str | None = None,
) -> dict[str, object]:
    """Safe metadata for an LLM-policy-denied event (reason code only)."""

    meta = _base(repository_key, structural_change_id, normalized_event_key)
    meta["policy_allowed"] = False
    meta["reason"] = reason
    meta["result_type"] = "llm_policy_denied"
    return meta


def budget_blocked_metadata(
    *,
    repository_key: str,
    structural_change_id: str,
    normalized_event_key: str | None = None,
) -> dict[str, object]:
    """Safe metadata for a token-budget-exceeded event."""

    meta = _base(repository_key, structural_change_id, normalized_event_key)
    meta["result_type"] = "budget_exceeded"
    return meta


def provider_error_metadata(
    *,
    repository_key: str,
    structural_change_id: str,
    model_id: str,
    error_class: str,
    normalized_event_key: str | None = None,
) -> dict[str, object]:
    """Safe metadata for a provider-error event (error class only, no payload)."""

    meta = _base(repository_key, structural_change_id, normalized_event_key)
    meta["model_id"] = model_id
    meta["error_class"] = error_class
    meta["result_type"] = "provider_error"
    return meta


def invalid_output_metadata(
    *,
    repository_key: str,
    structural_change_id: str,
    model_id: str,
    normalized_event_key: str | None = None,
) -> dict[str, object]:
    """Safe metadata for an unparseable-output event (no draft body)."""

    meta = _base(repository_key, structural_change_id, normalized_event_key)
    meta["model_id"] = model_id
    meta["result_type"] = "invalid_output"
    return meta


def succeeded_metadata(
    *,
    repository_key: str,
    structural_change_id: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    content_hash: str,
    citation_count: int,
    normalized_event_key: str | None = None,
) -> dict[str, object]:
    """Safe metadata for a draft-produced event (counts and hash only)."""

    meta = _base(repository_key, structural_change_id, normalized_event_key)
    meta["model_id"] = model_id
    meta["input_tokens"] = input_tokens
    meta["output_tokens"] = output_tokens
    meta["total_tokens"] = input_tokens + output_tokens
    meta["content_hash"] = content_hash
    meta["citation_count"] = citation_count
    meta["result_type"] = "drafted"
    return meta


def completed_metadata(
    *,
    repository_key: str,
    structural_change_id: str,
    result_type: str,
    normalized_event_key: str | None = None,
) -> dict[str, object]:
    """Safe metadata for the terminal drafting-completed event."""

    meta = _base(repository_key, structural_change_id, normalized_event_key)
    meta["result_type"] = result_type
    return meta


__all__ = [
    "DRAFTING_STARTED",
    "DRAFTING_POLICY_BLOCKED",
    "DRAFTING_BUDGET_BLOCKED",
    "DRAFTING_PROVIDER_ERROR",
    "DRAFTING_INVALID_OUTPUT",
    "DRAFTING_SUCCEEDED",
    "DRAFTING_COMPLETED",
    "ALLOWED_METADATA_KEYS",
    "started_metadata",
    "policy_blocked_metadata",
    "budget_blocked_metadata",
    "provider_error_metadata",
    "invalid_output_metadata",
    "succeeded_metadata",
    "completed_metadata",
]
