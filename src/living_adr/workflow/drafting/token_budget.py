"""Deterministic token budgeter for prompt packing (feature 008, S-004, US-4).

Prompt cost/limit control must be deterministic and must never silently drop the
evidence a draft is grounded in. This module:

* enforces a configurable budget (default :data:`DEFAULT_PROMPT_BUDGET` = 8,000
  prompt tokens, FR-6);
* always keeps ``required`` sections (the structural summary and evidence);
* keeps optional sections in priority order, deterministically truncating the
  rest with an explicit omitted-context note (US-4); and
* **blocks** — signalling the caller to make no Claude call — when the required
  sections alone exceed the budget (US-4).

The estimator is an injectable abstraction so a future tokenizer can replace the
heuristic without touching callers; the heuristic is deterministic (~4 chars per
token) so identical inputs always budget identically (NFR-3).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

#: Default prompt-token budget (FR-6; autopilot default).
DEFAULT_PROMPT_BUDGET = 8000


@runtime_checkable
class TokenEstimator(Protocol):
    """Estimates the token count of a text fragment."""

    def estimate(self, text: str) -> int: ...


class HeuristicTokenEstimator:
    """Deterministic, dependency-free estimator (~4 characters per token)."""

    def estimate(self, text: str) -> int:
        return max(0, (len(text) + 3) // 4)


class BudgetConfig(BaseModel):
    """Prompt budget configuration."""

    model_config = ConfigDict(frozen=True)

    max_prompt_tokens: int = DEFAULT_PROMPT_BUDGET


class BudgetStatus(StrEnum):
    """Outcome of a budgeting pass."""

    FIT = "fit"
    TRUNCATED = "truncated"
    BLOCKED = "blocked"


class PromptSection(BaseModel):
    """One prompt section with a required flag and a priority (lower = kept first)."""

    model_config = ConfigDict(frozen=True)

    name: str
    content: str
    required: bool = False
    priority: int = 100


class BudgetResult(BaseModel):
    """The result of applying a budget to an ordered set of sections."""

    model_config = ConfigDict(frozen=True)

    status: BudgetStatus
    included: tuple[PromptSection, ...] = ()
    omitted: tuple[PromptSection, ...] = ()
    total_tokens: int = 0
    note: str = ""


def _ordered(sections: list[PromptSection]) -> list[PromptSection]:
    # Stable, deterministic ordering: priority then name.
    return sorted(sections, key=lambda s: (s.priority, s.name))


def apply_budget(
    sections: list[PromptSection],
    estimator: TokenEstimator,
    config: BudgetConfig,
) -> BudgetResult:
    """Apply ``config``'s budget to ``sections`` deterministically.

    Required sections are reserved first; if they alone exceed the budget the
    result is :attr:`BudgetStatus.BLOCKED` with no included sections (the caller
    must not call Claude). Otherwise optional sections are added in priority order
    until the budget is reached; any that do not fit are omitted and reported in
    :attr:`BudgetResult.note` (:attr:`BudgetStatus.TRUNCATED`).
    """

    ordered = _ordered(sections)
    budget = config.max_prompt_tokens

    required = [s for s in ordered if s.required]
    optional = [s for s in ordered if not s.required]

    required_tokens = sum(estimator.estimate(s.content) for s in required)
    if required_tokens > budget:
        return BudgetResult(
            status=BudgetStatus.BLOCKED,
            included=(),
            omitted=tuple(required + optional),
            total_tokens=required_tokens,
            note=(
                "Required sections "
                f"({', '.join(s.name for s in required)}) exceed the prompt "
                f"budget of {budget} tokens; drafting blocked (no Claude call)."
            ),
        )

    included = list(required)
    omitted: list[PromptSection] = []
    total = required_tokens
    for section in optional:
        cost = estimator.estimate(section.content)
        if total + cost <= budget:
            included.append(section)
            total += cost
        else:
            omitted.append(section)

    if omitted:
        status = BudgetStatus.TRUNCATED
        note = (
            "Optional context omitted to fit the prompt budget: "
            f"{', '.join(s.name for s in omitted)}."
        )
    else:
        status = BudgetStatus.FIT
        note = ""

    # Re-order included sections deterministically for stable prompt rendering.
    included = _ordered(included)
    return BudgetResult(
        status=status,
        included=tuple(included),
        omitted=tuple(omitted),
        total_tokens=total,
        note=note,
    )


__all__ = [
    "DEFAULT_PROMPT_BUDGET",
    "TokenEstimator",
    "HeuristicTokenEstimator",
    "BudgetConfig",
    "BudgetStatus",
    "PromptSection",
    "BudgetResult",
    "apply_budget",
]
