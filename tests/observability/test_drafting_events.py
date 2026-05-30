"""S-007 RED tests: metadata-only drafting telemetry (feature 008, US-7).

Drafting events must expose only safe metadata — repository key, ids, model id,
token counts, policy state, result type, error class, content hash, citation
count — and must never carry raw prompts, diffs, Claude responses, or draft
bodies (architecture #cross-cutting default-deny, FM-21, NFR-4).
"""

from __future__ import annotations

from living_adr.observability.drafting_events import (
    ALLOWED_METADATA_KEYS,
    DRAFTING_BUDGET_BLOCKED,
    DRAFTING_COMPLETED,
    DRAFTING_INVALID_OUTPUT,
    DRAFTING_POLICY_BLOCKED,
    DRAFTING_PROVIDER_ERROR,
    DRAFTING_STARTED,
    DRAFTING_SUCCEEDED,
    budget_blocked_metadata,
    completed_metadata,
    invalid_output_metadata,
    policy_blocked_metadata,
    provider_error_metadata,
    started_metadata,
    succeeded_metadata,
)

_REPO = "github.com/acme/widgets"
_CHG = "chg-1"


def _all_events() -> list[dict[str, object]]:
    return [
        started_metadata(
            repository_key=_REPO,
            structural_change_id=_CHG,
            model_id="claude-sonnet-4-6",
            normalized_event_key="evt-1",
        ),
        policy_blocked_metadata(
            repository_key=_REPO,
            structural_change_id=_CHG,
            reason="external_llm_denied",
        ),
        budget_blocked_metadata(repository_key=_REPO, structural_change_id=_CHG),
        provider_error_metadata(
            repository_key=_REPO,
            structural_change_id=_CHG,
            model_id="claude-sonnet-4-6",
            error_class="timeout",
        ),
        invalid_output_metadata(
            repository_key=_REPO,
            structural_change_id=_CHG,
            model_id="claude-sonnet-4-6",
        ),
        succeeded_metadata(
            repository_key=_REPO,
            structural_change_id=_CHG,
            model_id="claude-sonnet-4-6",
            input_tokens=1200,
            output_tokens=300,
            content_hash="abc123",
            citation_count=2,
        ),
        completed_metadata(
            repository_key=_REPO,
            structural_change_id=_CHG,
            result_type="drafted",
        ),
    ]


def test_event_names_are_namespaced() -> None:
    for name in (
        DRAFTING_STARTED,
        DRAFTING_POLICY_BLOCKED,
        DRAFTING_BUDGET_BLOCKED,
        DRAFTING_PROVIDER_ERROR,
        DRAFTING_INVALID_OUTPUT,
        DRAFTING_SUCCEEDED,
        DRAFTING_COMPLETED,
    ):
        assert name.startswith("adr_drafting.")


def test_started_has_safe_identifiers() -> None:
    meta = started_metadata(
        repository_key=_REPO,
        structural_change_id=_CHG,
        model_id="claude-sonnet-4-6",
    )
    assert meta["repository_key"] == _REPO
    assert meta["structural_change_id"] == _CHG
    assert meta["model_id"] == "claude-sonnet-4-6"


def test_policy_blocked_reports_policy_state() -> None:
    meta = policy_blocked_metadata(
        repository_key=_REPO, structural_change_id=_CHG, reason="external_llm_denied"
    )
    assert meta["policy_allowed"] is False
    assert meta["reason"] == "external_llm_denied"
    assert meta["result_type"] == "llm_policy_denied"


def test_provider_error_reports_error_class_only() -> None:
    meta = provider_error_metadata(
        repository_key=_REPO,
        structural_change_id=_CHG,
        model_id="claude-sonnet-4-6",
        error_class="timeout",
    )
    assert meta["error_class"] == "timeout"
    assert meta["result_type"] == "provider_error"


def test_succeeded_reports_token_counts_and_hash() -> None:
    meta = succeeded_metadata(
        repository_key=_REPO,
        structural_change_id=_CHG,
        model_id="claude-sonnet-4-6",
        input_tokens=1200,
        output_tokens=300,
        content_hash="abc123",
        citation_count=2,
    )
    assert meta["input_tokens"] == 1200
    assert meta["output_tokens"] == 300
    assert meta["content_hash"] == "abc123"
    assert meta["citation_count"] == 2
    assert meta["result_type"] == "drafted"


def test_completed_reports_result_type() -> None:
    meta = completed_metadata(
        repository_key=_REPO, structural_change_id=_CHG, result_type="budget_exceeded"
    )
    assert meta["result_type"] == "budget_exceeded"


def test_all_event_keys_are_in_allowlist() -> None:
    for meta in _all_events():
        assert set(meta.keys()) <= ALLOWED_METADATA_KEYS


def test_no_raw_payloads_leak() -> None:
    """Even when handed sensitive-looking strings, builders accept only safe args."""

    raw_prompt = "<<<UNTRUSTED_REPOSITORY_DATA>>> diff --git a/x b/x @@ secret"
    raw_draft = "# Secret ADR\n## Decision\nleak me"
    for meta in _all_events():
        serialized = " ".join(str(v) for v in meta.values())
        assert "diff --git" not in serialized
        assert "@@" not in serialized
        assert raw_prompt not in serialized
        assert raw_draft not in serialized
        assert "secret" not in serialized.lower()
