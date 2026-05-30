"""S-004 RED tests: deterministic token budgeter (feature 008, US-4).

The budgeter enforces a default 8,000-token prompt budget, always keeps required
sections (structural summary + evidence), deterministically truncates optional
context with an explicit omitted note, and *blocks* (no Claude call) when the
required sections alone cannot fit.
"""

from __future__ import annotations

from living_adr.workflow.drafting.token_budget import (
    DEFAULT_PROMPT_BUDGET,
    BudgetConfig,
    BudgetStatus,
    HeuristicTokenEstimator,
    PromptSection,
    apply_budget,
)


def _estimator() -> HeuristicTokenEstimator:
    return HeuristicTokenEstimator()


def test_default_budget_is_8000() -> None:
    assert DEFAULT_PROMPT_BUDGET == 8000
    assert BudgetConfig().max_prompt_tokens == 8000


def test_all_sections_fit() -> None:
    sections = [
        PromptSection(name="template", content="a" * 40, required=True, priority=0),
        PromptSection(name="evidence", content="b" * 40, required=True, priority=1),
        PromptSection(name="context", content="c" * 40, required=False, priority=2),
    ]
    result = apply_budget(sections, _estimator(), BudgetConfig())
    assert result.status is BudgetStatus.FIT
    assert {s.name for s in result.included} == {"template", "evidence", "context"}
    assert result.omitted == ()


def test_optional_sections_truncated_with_note() -> None:
    config = BudgetConfig(max_prompt_tokens=30)  # ~120 chars
    sections = [
        PromptSection(name="template", content="a" * 40, required=True, priority=0),
        PromptSection(name="evidence", content="b" * 40, required=True, priority=1),
        PromptSection(name="context", content="c" * 200, required=False, priority=2),
    ]
    result = apply_budget(sections, _estimator(), config)
    assert result.status is BudgetStatus.TRUNCATED
    assert {s.name for s in result.included} == {"template", "evidence"}
    assert {s.name for s in result.omitted} == {"context"}
    assert "context" in result.note
    assert "omitted" in result.note.lower()


def test_higher_priority_optional_kept_first() -> None:
    config = BudgetConfig(max_prompt_tokens=30)  # ~120 chars
    sections = [
        PromptSection(name="required", content="a" * 40, required=True, priority=0),
        PromptSection(name="keep", content="b" * 40, required=False, priority=1),
        PromptSection(name="drop", content="c" * 200, required=False, priority=2),
    ]
    result = apply_budget(sections, _estimator(), config)
    assert result.status is BudgetStatus.TRUNCATED
    included = {s.name for s in result.included}
    assert "required" in included and "keep" in included
    assert "drop" not in included


def test_required_sections_exceeding_budget_block() -> None:
    config = BudgetConfig(max_prompt_tokens=10)  # ~40 chars
    sections = [
        PromptSection(name="template", content="a" * 80, required=True, priority=0),
        PromptSection(name="evidence", content="b" * 80, required=True, priority=1),
        PromptSection(name="context", content="c" * 40, required=False, priority=2),
    ]
    result = apply_budget(sections, _estimator(), config)
    assert result.status is BudgetStatus.BLOCKED
    assert result.included == ()
    assert "block" in result.note.lower()


def test_budget_is_deterministic() -> None:
    config = BudgetConfig(max_prompt_tokens=30)
    sections = [
        PromptSection(name="required", content="a" * 40, required=True, priority=0),
        PromptSection(name="opt", content="c" * 200, required=False, priority=2),
    ]
    first = apply_budget(sections, _estimator(), config)
    second = apply_budget(sections, _estimator(), config)
    assert first == second
