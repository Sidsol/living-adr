"""Evaluation runner / CLI entry point (feature 013, slice 5).

Provides offline, deterministic execution of the retrieval and drafting harnesses
against versioned YAML fixtures, plus a JSON-emitting CLI suitable for local runs
and CI gating. The runner uses replay providers built from each fixture's recorded
sample output, so it never performs live retrieval or Claude calls.

Exit code is non-zero when a regression signal is raised, so CI can gate on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.repository import RepositoryIdentity
from living_adr.observability.evals.drafting import (
    DraftingEvalReport,
    evaluate_drafting,
    replay_provider,
)
from living_adr.observability.evals.fixtures import (
    HeldoutQueryCase,
    RetrievalFixture,
    load_drafting_fixture,
    load_retrieval_fixture,
)
from living_adr.observability.evals.retrieval import (
    RetrievalEvalReport,
    evaluate_retrieval,
)

try:
    from living_adr.core.graph.models import WhyAnswer
except Exception:  # pragma: no cover - defensive
    WhyAnswer = None  # type: ignore[assignment,misc]


class ReplayQuery:
    """Offline :class:`ArchitectureContextQuery` that replays fixture samples.

    Keyed by ``(repository_key, question)`` so the retrieval evaluator can run
    deterministically with no graph backend.
    """

    def __init__(self, fixture: RetrievalFixture) -> None:
        self._by_question: dict[tuple[str, str], HeldoutQueryCase] = {
            (case.repository_key, case.question): case for case in fixture.cases
        }

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
        snapshot: object | None = None,
        limit: int = 5,
    ) -> object:
        case = self._by_question[(repository.key, question)]
        sample = case.sample_answer
        if WhyAnswer is None:  # pragma: no cover - defensive
            raise RuntimeError("WhyAnswer model unavailable")
        return WhyAnswer(
            repository=repository,
            question=question,
            answer=sample.answer,
            adr_id=sample.adr_id,
            citations=tuple(sample.citations),
            found=sample.found,
        )

    def traverse_from_code_area(self, *args: object, **kwargs: object) -> list:
        return []


def run_retrieval(
    fixture_path: str | Path,
    *,
    obs: Observability | None = None,
    relevance_threshold: float = 1.0,
    baseline_pass_rate: float | None = None,
) -> RetrievalEvalReport:
    """Load a retrieval fixture and evaluate it with the offline replay query."""

    fixture = load_retrieval_fixture(fixture_path)
    query = ReplayQuery(fixture)
    return evaluate_retrieval(
        fixture,
        query,
        obs=obs or NoOpObservability(),
        relevance_threshold=relevance_threshold,
        baseline_pass_rate=baseline_pass_rate,
    )


def run_drafting(
    fixture_path: str | Path,
    *,
    obs: Observability | None = None,
) -> DraftingEvalReport:
    """Load a drafting fixture and evaluate it with the offline replay provider."""

    fixture = load_drafting_fixture(fixture_path)
    return evaluate_drafting(
        fixture, replay_provider, obs=obs or NoOpObservability()
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: emit machine-readable JSON; exit non-zero on a regression signal."""

    parser = argparse.ArgumentParser(prog="living-adr-evals")
    parser.add_argument("--retrieval", help="path to a retrieval fixture YAML")
    parser.add_argument("--drafting", help="path to a drafting fixture YAML")
    parser.add_argument(
        "--relevance-threshold",
        type=float,
        default=1.0,
        help="minimum retrieval pass rate before a regression is flagged",
    )
    args = parser.parse_args(argv)

    if not args.retrieval and not args.drafting:
        parser.error("provide --retrieval and/or --drafting")

    output: dict[str, object] = {}
    regression = False

    if args.retrieval:
        report = run_retrieval(
            args.retrieval, relevance_threshold=args.relevance_threshold
        )
        output["retrieval"] = report.to_dict()
        regression = regression or report.regression

    if args.drafting:
        report_d = run_drafting(args.drafting)
        output["drafting"] = report_d.to_dict()
        regression = regression or report_d.regression

    print(json.dumps(output, indent=2, sort_keys=True))
    return 1 if regression else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))


__all__ = ["ReplayQuery", "run_retrieval", "run_drafting", "main"]
