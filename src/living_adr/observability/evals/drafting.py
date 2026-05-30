"""Drafting evaluation harness (feature 013, slice 5; SM-04 drafting).

Validates ADR draft outputs for four structural quality signals: evidence
citation, alternatives considered, consequences stated, and provisional-rationale
labeling. A ``DraftProvider`` yields the evaluable signals for each case (tests
inject fakes; the runner replays fixture ``sample_draft`` values), so evaluation
runs entirely offline with no Claude calls.

The aggregate report is machine-readable. ``regression`` is truthy when any case's
observed pass/fail diverges from its expected outcome, giving a failing signal for
CI when a previously-good draft check degrades (FM-22: signal, not proof).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.observability.evals.fixtures import (
    DraftingCase,
    DraftingFixture,
    SampleDraft,
)


@dataclass(frozen=True)
class DraftEvaluable:
    """The four structural signals an ADR draft is checked against."""

    cites_evidence: bool = False
    lists_alternatives: bool = False
    states_consequences: bool = False
    labeled_provisional: bool = False


# A provider maps a case to the draft signals to evaluate.
DraftProvider = Callable[[DraftingCase], DraftEvaluable]


def replay_provider(case: DraftingCase) -> DraftEvaluable:
    """Offline provider: replay the fixture's recorded ``sample_draft`` signals."""

    sample: SampleDraft = case.sample_draft
    return DraftEvaluable(
        cites_evidence=sample.cites_evidence,
        lists_alternatives=sample.lists_alternatives,
        states_consequences=sample.states_consequences,
        labeled_provisional=sample.labeled_provisional,
    )


@dataclass(frozen=True)
class DraftingCaseResult:
    """Per-case drafting evaluation outcome."""

    case_id: str
    repository_key: str
    evidence_citation_pass: bool
    alternatives_pass: bool
    consequences_pass: bool
    provisional_label_pass: bool
    passed: bool
    expected_pass: bool
    matches_expectation: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "repository": self.repository_key,
            "evidence_citation_pass": self.evidence_citation_pass,
            "alternatives_pass": self.alternatives_pass,
            "consequences_pass": self.consequences_pass,
            "provisional_label_pass": self.provisional_label_pass,
            "passed": self.passed,
            "expected_pass": self.expected_pass,
            "matches_expectation": self.matches_expectation,
        }


@dataclass(frozen=True)
class DraftingEvalReport:
    """Aggregate, machine-readable drafting evaluation report."""

    version: str
    results: tuple[DraftingCaseResult, ...]
    regression: bool = False

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def matches_count(self) -> int:
        return sum(1 for r in self.results if r.matches_expectation)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "drafting_eval",
            "version": self.version,
            "total": self.total,
            "passed": self.passed_count,
            "matches_expectation": self.matches_count,
            "regression": self.regression,
            "results": [r.to_dict() for r in self.results],
        }


def _check(required: bool, present: bool) -> bool:
    """A dimension passes if not required, or required and present."""

    return (not required) or present


def _evaluate_case(
    case: DraftingCase, draft: DraftEvaluable
) -> DraftingCaseResult:
    evidence = _check(case.require_evidence_citation, draft.cites_evidence)
    alternatives = _check(case.require_alternatives, draft.lists_alternatives)
    consequences = _check(case.require_consequences, draft.states_consequences)
    provisional = _check(case.require_provisional_label, draft.labeled_provisional)
    passed = evidence and alternatives and consequences and provisional
    return DraftingCaseResult(
        case_id=case.case_id,
        repository_key=case.repository_key,
        evidence_citation_pass=evidence,
        alternatives_pass=alternatives,
        consequences_pass=consequences,
        provisional_label_pass=provisional,
        passed=passed,
        expected_pass=case.expected_pass,
        matches_expectation=(passed == case.expected_pass),
    )


def evaluate_drafting(
    fixture: DraftingFixture,
    provider: DraftProvider = replay_provider,
    *,
    obs: Observability | None = None,
) -> DraftingEvalReport:
    """Evaluate every drafting case and return a regression-aware report.

    ``regression`` is truthy when any case's observed pass/fail diverges from the
    fixture's ``expected_pass`` — i.e. a draft check changed unexpectedly.
    """

    obs = obs or NoOpObservability()
    results = tuple(
        _evaluate_case(case, provider(case)) for case in fixture.cases
    )
    regression = any(not r.matches_expectation for r in results)

    for r in results:
        obs.record_event(
            "eval.drafting.case",
            {
                "repository": r.repository_key,
                "case_id": r.case_id,
                "passed": r.passed,
                "matches_expectation": r.matches_expectation,
            },
        )

    report = DraftingEvalReport(
        version=fixture.version, results=results, regression=regression
    )
    obs.record_event(
        "eval.drafting.summary",
        {
            "version": fixture.version,
            "total": report.total,
            "passed": report.passed_count,
            "matches_expectation": report.matches_count,
            "regression": report.regression,
        },
    )
    return report


__all__ = [
    "DraftEvaluable",
    "DraftProvider",
    "replay_provider",
    "DraftingCaseResult",
    "DraftingEvalReport",
    "evaluate_drafting",
]
