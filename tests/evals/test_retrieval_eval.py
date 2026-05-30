"""Slice 5: retrieval evaluation harness (SM-03/SM-04).

Uses a fake/replay ``ArchitectureContextQuery`` — no graph backend, no network.
Asserts per-query hit/miss reporting, relevance + coverage signals, and the
machine-readable regression flag.
"""

from __future__ import annotations

from pathlib import Path

from living_adr.core.graph.models import WhyAnswer
from living_adr.core.repository import RepositoryIdentity
from living_adr.observability.evals.fixtures import (
    HeldoutQueryCase,
    RetrievalFixture,
    SampleAnswer,
    load_retrieval_fixture,
)
from living_adr.observability.evals.retrieval import (
    evaluate_retrieval,
    identity_from_key,
)
from living_adr.observability.evals.runner import ReplayQuery, run_retrieval

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "evals"
    / "heldout_queries.example.yaml"
)


class FakeObservability:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def record_event(self, name, metadata=None):
        self.events.append((name, dict(metadata or {})))

    def increment_counter(self, name, value=1, metadata=None):
        pass

    def start_span(self, name, metadata=None):  # pragma: no cover
        raise NotImplementedError


def test_identity_from_key_roundtrip() -> None:
    ident = identity_from_key("github.com/acme/living-adr")
    assert isinstance(ident, RepositoryIdentity)
    assert ident.key == "github.com/acme/living-adr"


def test_example_fixture_has_version_and_edge_case() -> None:
    fixture = load_retrieval_fixture(FIXTURE)
    assert fixture.version
    assert fixture.has_edge_case is True


def test_replay_query_passes_all_example_cases() -> None:
    fixture = load_retrieval_fixture(FIXTURE)
    obs = FakeObservability()
    report = evaluate_retrieval(fixture, ReplayQuery(fixture), obs=obs)
    assert report.total == 3
    assert report.failed_count == 0
    assert report.regression is False
    # Machine-readable shape.
    data = report.to_dict()
    assert data["kind"] == "retrieval_eval"
    assert data["passed"] == 3
    # Per-query hit/miss reporting present.
    first = data["results"][0]
    assert "hit_adr_ids" in first and "missing_adr_ids" in first
    assert first["relevance_pass"] is True and first["coverage_pass"] is True
    # Summary + per-case events emitted (safe metadata only).
    assert any(n == "eval.retrieval.summary" for n, _ in obs.events)


def test_runner_run_retrieval_matches_direct_eval() -> None:
    report = run_retrieval(FIXTURE)
    assert report.passed_count == 3
    assert report.regression is False


def test_missing_citation_produces_relevance_failure_and_regression() -> None:
    # A query whose answer omits the expected ADR -> relevance miss.
    case = HeldoutQueryCase(
        case_id="q-miss",
        repository_key="github.com/o/r",
        question="why X?",
        expected_adr_ids=("ADR-0001",),
        expected_answerable=True,
        sample_answer=SampleAnswer(
            adr_id="ADR-9999", citations=("ADR-9999",), found=True
        ),
    )
    fixture = RetrievalFixture(version="t", cases=(case,))
    report = evaluate_retrieval(fixture, ReplayQuery(fixture))
    result = report.results[0]
    assert result.relevance_pass is False
    assert result.missing_adr_ids == ("ADR-0001",)
    assert report.regression is True


def test_unanswerable_case_with_found_true_fails_coverage() -> None:
    case = HeldoutQueryCase(
        case_id="q-cov",
        repository_key="github.com/o/r",
        question="future?",
        expected_adr_ids=(),
        expected_answerable=False,
        sample_answer=SampleAnswer(found=True),
    )
    fixture = RetrievalFixture(version="t", cases=(case,))
    report = evaluate_retrieval(fixture, ReplayQuery(fixture))
    assert report.results[0].coverage_pass is False
    assert report.regression is True


def test_replay_query_returns_whyanswer() -> None:
    fixture = load_retrieval_fixture(FIXTURE)
    query = ReplayQuery(fixture)
    ident = identity_from_key("github.com/acme/living-adr")
    answer = query.answer_why(
        ident, "Why did we choose PostgreSQL for the context store?"
    )
    assert isinstance(answer, WhyAnswer)
    assert answer.found is True
    assert "ADR-0007" in answer.citations
