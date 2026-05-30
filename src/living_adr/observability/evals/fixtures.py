"""Versioned evaluation fixture schemas (feature 013, slice 5).

Typed, frozen fixture models for held-out retrieval queries (SM-03/SM-04) and
drafting quality cases (SM-04 drafting). Fixtures carry a ``version`` so baselines
are reproducible and evaluation overfitting (FM-22) is auditable. Each fixture
must include at least one case, and the example fixtures include an edge/rejected
case so the harness exercises the unanswerable/deficient path.

Each case carries a *sample* output (``sample_answer`` / ``sample_draft``) used by
the offline runner/CLI to replay deterministic results without live retrieval or
Claude calls. Tests may instead inject their own query/draft providers.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SampleAnswer(_Frozen):
    """Replayable retrieval answer for offline/example runs."""

    adr_id: str | None = None
    citations: tuple[str, ...] = ()
    found: bool = False
    answer: str = ""


class HeldoutQueryCase(_Frozen):
    """A single held-out retrieval query with expected citations/coverage."""

    case_id: str
    repository_key: str
    question: str
    code_area_id: str | None = None
    expected_adr_ids: tuple[str, ...] = ()
    expected_references: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    edge_case: bool = False
    expected_answerable: bool = True
    sample_answer: SampleAnswer = SampleAnswer()


class RetrievalFixture(_Frozen):
    """Versioned collection of held-out retrieval cases."""

    version: str
    cases: tuple[HeldoutQueryCase, ...]

    @field_validator("cases")
    @classmethod
    def _non_empty(
        cls, cases: tuple[HeldoutQueryCase, ...]
    ) -> tuple[HeldoutQueryCase, ...]:
        if not cases:
            raise ValueError("a retrieval fixture must contain at least one case")
        return cases

    @property
    def has_edge_case(self) -> bool:
        return any(case.edge_case for case in self.cases)


class SampleDraft(_Frozen):
    """Replayable drafting signals for offline/example runs."""

    cites_evidence: bool = False
    lists_alternatives: bool = False
    states_consequences: bool = False
    labeled_provisional: bool = False


class DraftingCase(_Frozen):
    """A drafting quality case with required structural checks."""

    case_id: str
    repository_key: str
    require_evidence_citation: bool = True
    require_alternatives: bool = True
    require_consequences: bool = True
    require_provisional_label: bool = True
    labels: tuple[str, ...] = ()
    edge_case: bool = False
    expected_pass: bool = True
    sample_draft: SampleDraft = SampleDraft()


class DraftingFixture(_Frozen):
    """Versioned collection of drafting cases."""

    version: str
    cases: tuple[DraftingCase, ...]

    @field_validator("cases")
    @classmethod
    def _non_empty(
        cls, cases: tuple[DraftingCase, ...]
    ) -> tuple[DraftingCase, ...]:
        if not cases:
            raise ValueError("a drafting fixture must contain at least one case")
        return cases

    @property
    def has_edge_case(self) -> bool:
        return any(case.edge_case for case in self.cases)


def load_retrieval_fixture(path: str | Path) -> RetrievalFixture:
    """Parse a YAML held-out query fixture into a :class:`RetrievalFixture`."""

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return RetrievalFixture.model_validate(data)


def load_drafting_fixture(path: str | Path) -> DraftingFixture:
    """Parse a YAML drafting fixture into a :class:`DraftingFixture`."""

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return DraftingFixture.model_validate(data)


__all__ = [
    "SampleAnswer",
    "HeldoutQueryCase",
    "RetrievalFixture",
    "SampleDraft",
    "DraftingCase",
    "DraftingFixture",
    "load_retrieval_fixture",
    "load_drafting_fixture",
]
