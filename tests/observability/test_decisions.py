"""Slice 4: draft outcome and mutation authorization observability (SM-01/SM-05).

Helpers emit safe, identifier-only metadata for HITL draft decisions and
approval-bound graph mutations. They never carry ADR body text, reviewer
comments, or raw draft content. Tests use an in-memory fake port — no network.
"""

from __future__ import annotations

from collections.abc import Mapping

from living_adr.core.approval import (
    ApprovalRequiredError,
    DecisionAlreadyConsumedError,
    DecisionRepositoryMismatchError,
    DraftContentMismatchError,
    MutationFingerprintMismatchError,
)
from living_adr.observability import decisions
from living_adr.observability.decisions import (
    DecisionEvent,
    DraftOutcome,
    MutationAuthFailure,
    failure_reason_for,
)
from living_adr.observability.redaction import redact_metadata

REPO = "github.com/o/r"


class FakeObservability:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []
        self.counters: list[tuple[str, int, dict]] = []

    def record_event(self, name, metadata=None):
        self.events.append((name, dict(metadata or {})))

    def increment_counter(self, name, value=1, metadata=None):
        self.counters.append((name, value, dict(metadata or {})))

    def start_span(self, name, metadata=None):  # pragma: no cover
        raise NotImplementedError


def _assert_redaction_safe(metadata: Mapping[str, object]) -> None:
    result = redact_metadata("probe", dict(metadata))
    assert result.safe == dict(metadata)
    assert result.redactions == ()


# ----------------------------------------------------------------- draft outcomes


def test_record_draft_outcome_has_only_safe_identifiers() -> None:
    obs = FakeObservability()
    decisions.record_draft_outcome(
        obs,
        repository_key=REPO,
        draft_id="draft-7",
        change_class="structural",
        outcome=DraftOutcome.APPROVED_AFTER_EDIT,
        reviewer_role="tech_lead",
    )
    name, value, meta = obs.counters[0]
    assert name == DecisionEvent.DRAFT_OUTCOME
    assert value == 1
    assert meta == {
        "repository": REPO,
        "draft_id": "draft-7",
        "change_class": "structural",
        "outcome": "approved_after_edit",
        "reviewer_role": "tech_lead",
    }
    _assert_redaction_safe(meta)


def test_draft_outcome_enum_covers_all_decisions() -> None:
    assert {o.value for o in DraftOutcome} == {
        "approved",
        "approved_after_edit",
        "rejected",
        "deferred",
    }


def test_record_draft_outcome_never_emits_body_or_comment() -> None:
    obs = FakeObservability()
    decisions.record_draft_outcome(
        obs,
        repository_key=REPO,
        draft_id="d1",
        change_class="behavioral",
        outcome=DraftOutcome.REJECTED,
        reviewer_role="architect",
    )
    _, _, meta = obs.counters[0]
    assert "adr_body" not in meta
    assert "reviewer_comment" not in meta
    assert "draft_body" not in meta


# ------------------------------------------------------ unauthorized mutations


def test_record_unauthorized_mutation_emits_reason_and_safe_ids() -> None:
    obs = FakeObservability()
    decisions.record_unauthorized_mutation(
        obs,
        repository_key=REPO,
        mutation_type="upsert_adr_node",
        reason=MutationAuthFailure.FINGERPRINT_MISMATCH,
        decision_id="dec-9",
    )
    name, meta = obs.events[0]
    assert name == DecisionEvent.MUTATION_UNAUTHORIZED
    assert meta["reason"] == "fingerprint_mismatch"
    assert meta["mutation_type"] == "upsert_adr_node"
    assert meta["decision_id"] == "dec-9"
    assert meta["repository"] == REPO
    _assert_redaction_safe(meta)


def test_unauthorized_mutation_reason_codes_cover_required_set() -> None:
    values = {r.value for r in MutationAuthFailure}
    for required in (
        "missing_or_unapproved",
        "expired",
        "reused",
        "fingerprint_mismatch",
        "rejected",
    ):
        assert required in values


def test_failure_reason_for_maps_approval_errors() -> None:
    assert (
        failure_reason_for(ApprovalRequiredError("x"))
        == MutationAuthFailure.MISSING_OR_UNAPPROVED
    )
    assert (
        failure_reason_for(DecisionAlreadyConsumedError("x"))
        == MutationAuthFailure.REUSED
    )
    assert (
        failure_reason_for(MutationFingerprintMismatchError("x"))
        == MutationAuthFailure.FINGERPRINT_MISMATCH
    )
    assert (
        failure_reason_for(DecisionRepositoryMismatchError("x"))
        == MutationAuthFailure.REPOSITORY_MISMATCH
    )
    assert (
        failure_reason_for(DraftContentMismatchError("x"))
        == MutationAuthFailure.CONTENT_DRIFT
    )


def test_record_unauthorized_mutation_without_decision_id() -> None:
    obs = FakeObservability()
    decisions.record_unauthorized_mutation(
        obs,
        repository_key=REPO,
        mutation_type="add_relationship",
        reason=MutationAuthFailure.MISSING_OR_UNAPPROVED,
    )
    _, meta = obs.events[0]
    assert "decision_id" not in meta
    _assert_redaction_safe(meta)


# -------------------------------------------------------- authorized mutations


def test_record_authorized_mutation_has_safe_fields() -> None:
    obs = FakeObservability()
    decisions.record_authorized_mutation(
        obs,
        repository_key=REPO,
        decision_id="dec-1",
        mutation_type="supersede_adr",
        latency_ms=42,
    )
    name, meta = obs.events[0]
    assert name == DecisionEvent.MUTATION_AUTHORIZED
    assert meta["decision_id"] == "dec-1"
    assert meta["mutation_type"] == "supersede_adr"
    assert meta["latency_ms"] == 42
    assert meta["status"] == "success"
    assert "adr_body" not in meta
    _assert_redaction_safe(meta)
