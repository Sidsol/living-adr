"""Slice 5: drafting evaluation harness (SM-04 drafting).

Uses fake/replay draft providers — deterministic, no Claude calls. Asserts the
four structural quality checks, expectation matching, and the regression flag.
"""

from __future__ import annotations

from pathlib import Path

from living_adr.observability.evals.drafting import (
    DraftEvaluable,
    evaluate_drafting,
    replay_provider,
)
from living_adr.observability.evals.fixtures import (
    DraftingCase,
    DraftingFixture,
    load_drafting_fixture,
)
from living_adr.observability.evals.runner import run_drafting

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "evals"
    / "drafting_cases.example.yaml"
)


def test_example_fixture_has_version_and_edge_case() -> None:
    fixture = load_drafting_fixture(FIXTURE)
    assert fixture.version
    assert fixture.has_edge_case is True


def test_replay_provider_matches_all_expectations() -> None:
    fixture = load_drafting_fixture(FIXTURE)
    report = evaluate_drafting(fixture, replay_provider)
    # All three example cases match their expected_pass outcome.
    assert report.matches_count == 3
    assert report.regression is False
    data = report.to_dict()
    assert data["kind"] == "drafting_eval"
    first = data["results"][0]
    for dim in (
        "evidence_citation_pass",
        "alternatives_pass",
        "consequences_pass",
        "provisional_label_pass",
    ):
        assert dim in first


def test_deficient_case_is_detected_as_failing() -> None:
    fixture = load_drafting_fixture(FIXTURE)
    report = evaluate_drafting(fixture, replay_provider)
    deficient = next(
        r for r in report.results if r.case_id == "deficient-draft-missing-evidence"
    )
    assert deficient.passed is False
    assert deficient.evidence_citation_pass is False
    assert deficient.provisional_label_pass is False
    # Expected to fail, and it did -> matches expectation, no regression.
    assert deficient.matches_expectation is True


def test_unexpected_pass_raises_regression_signal() -> None:
    # A case the fixture expects to FAIL, but the provider returns a perfect draft.
    case = DraftingCase(
        case_id="should-fail-but-passes",
        repository_key="github.com/o/r",
        expected_pass=False,
    )
    fixture = DraftingFixture(version="t", cases=(case,))

    def perfect(_case: DraftingCase) -> DraftEvaluable:
        return DraftEvaluable(
            cites_evidence=True,
            lists_alternatives=True,
            states_consequences=True,
            labeled_provisional=True,
        )

    report = evaluate_drafting(fixture, perfect)
    assert report.results[0].passed is True
    assert report.results[0].matches_expectation is False
    assert report.regression is True


def test_runner_run_drafting_matches_direct_eval() -> None:
    report = run_drafting(FIXTURE)
    assert report.matches_count == 3
    assert report.regression is False
