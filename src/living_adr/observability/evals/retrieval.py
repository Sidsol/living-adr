"""Retrieval evaluation harness (feature 013, slice 5; SM-03/SM-04).

Runs held-out query fixtures against an :class:`ArchitectureContextQuery` and
reports, per query: which expected ADR citations were hit/missed, a relevance
pass/fail, and a coverage pass/fail (answerable vs. expected-answerable). The
aggregate report is machine-readable and exposes a ``regression`` flag that is
truthy when the configured threshold is violated — suitable for CI gating.

Scores are regression signals, not proof of correctness (FM-22).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.repository import RepositoryIdentity
from living_adr.observability.evals.fixtures import (
    HeldoutQueryCase,
    RetrievalFixture,
)

try:  # ArchitectureContextQuery is a typing-only Protocol; import is best-effort.
    from living_adr.core.graph.ports import ArchitectureContextQuery
except Exception:  # pragma: no cover - defensive
    ArchitectureContextQuery = object  # type: ignore[assignment,misc]


def identity_from_key(repository_key: str) -> RepositoryIdentity:
    """Build a :class:`RepositoryIdentity` from a canonical ``host/owner/repo`` key."""

    parts = repository_key.split("/")
    if len(parts) < 3:
        raise ValueError(
            f"repository_key must be 'host/owner/repo', got {repository_key!r}"
        )
    host, owner, repo = parts[0], parts[1], "/".join(parts[2:])
    return RepositoryIdentity(
        host=host, owner=owner, repo=repo, repo_id=repository_key
    )


@dataclass(frozen=True)
class RetrievalQueryResult:
    """Per-query retrieval evaluation outcome."""

    case_id: str
    repository_key: str
    expected_adr_ids: tuple[str, ...]
    hit_adr_ids: tuple[str, ...]
    missing_adr_ids: tuple[str, ...]
    relevance_pass: bool
    coverage_pass: bool
    answerable: bool
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "repository": self.repository_key,
            "expected_adr_ids": list(self.expected_adr_ids),
            "hit_adr_ids": list(self.hit_adr_ids),
            "missing_adr_ids": list(self.missing_adr_ids),
            "relevance_pass": self.relevance_pass,
            "coverage_pass": self.coverage_pass,
            "answerable": self.answerable,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class RetrievalEvalReport:
    """Aggregate, machine-readable retrieval evaluation report."""

    version: str
    results: tuple[RetrievalQueryResult, ...]
    relevance_threshold: float
    regression: bool = field(default=False)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        return self.total - self.passed_count

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "retrieval_eval",
            "version": self.version,
            "total": self.total,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "pass_rate": self.pass_rate,
            "relevance_threshold": self.relevance_threshold,
            "regression": self.regression,
            "results": [r.to_dict() for r in self.results],
        }


def _evaluate_case(
    case: HeldoutQueryCase, query: ArchitectureContextQuery
) -> RetrievalQueryResult:
    repository = identity_from_key(case.repository_key)
    answer = query.answer_why(
        repository,
        case.question,
        code_area_id=case.code_area_id,
    )

    cited: set[str] = set(answer.citations)
    if answer.adr_id:
        cited.add(answer.adr_id)

    expected = set(case.expected_adr_ids)
    hits = expected & cited
    missing = expected - cited

    if expected:
        relevance_pass = (len(hits) / len(expected)) >= 1.0
    else:
        # No citations expected (e.g. unanswerable case): relevance is vacuously
        # satisfied; coverage carries the signal.
        relevance_pass = True

    coverage_pass = bool(answer.found) == bool(case.expected_answerable)
    passed = relevance_pass and coverage_pass

    return RetrievalQueryResult(
        case_id=case.case_id,
        repository_key=case.repository_key,
        expected_adr_ids=tuple(case.expected_adr_ids),
        hit_adr_ids=tuple(sorted(hits)),
        missing_adr_ids=tuple(sorted(missing)),
        relevance_pass=relevance_pass,
        coverage_pass=coverage_pass,
        answerable=bool(answer.found),
        passed=passed,
    )


def evaluate_retrieval(
    fixture: RetrievalFixture,
    query: ArchitectureContextQuery,
    *,
    obs: Observability | None = None,
    relevance_threshold: float = 1.0,
    baseline_pass_rate: float | None = None,
) -> RetrievalEvalReport:
    """Evaluate every held-out query and return a regression-aware report.

    ``regression`` is truthy when the pass rate is below ``relevance_threshold``,
    or below ``baseline_pass_rate`` when a prior baseline is supplied.
    """

    obs = obs or NoOpObservability()
    results = tuple(_evaluate_case(case, query) for case in fixture.cases)
    report_results = results

    passed = sum(1 for r in results if r.passed)
    pass_rate = passed / len(results) if results else 0.0
    regression = pass_rate < relevance_threshold
    if baseline_pass_rate is not None:
        regression = regression or pass_rate < baseline_pass_rate

    for r in report_results:
        obs.record_event(
            "eval.retrieval.case",
            {
                "repository": r.repository_key,
                "case_id": r.case_id,
                "hit_count": len(r.hit_adr_ids),
                "miss_count": len(r.missing_adr_ids),
                "relevance_pass": r.relevance_pass,
                "coverage_pass": r.coverage_pass,
                "passed": r.passed,
            },
        )

    report = RetrievalEvalReport(
        version=fixture.version,
        results=report_results,
        relevance_threshold=relevance_threshold,
        regression=regression,
    )
    obs.record_event(
        "eval.retrieval.summary",
        {
            "version": fixture.version,
            "total": report.total,
            "passed": report.passed_count,
            "failed": report.failed_count,
            "regression": report.regression,
        },
    )
    return report


__all__ = [
    "identity_from_key",
    "RetrievalQueryResult",
    "RetrievalEvalReport",
    "evaluate_retrieval",
]
