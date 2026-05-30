"""Generic structural-change producer protocol and result (feature 004, S-001).

A *structural-change producer* turns Feature 003 candidate evidence into a typed
bundle of classified changes, no-ADR outcomes, and supporting evidence. Feature
004 ships the first concrete producer (the dependency classifier); Feature 005
adds schema/API producers behind the *same* protocol so workflow orchestration
and Feature 008 never special-case a classifier.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeEvidence,
    NoAdrOutcome,
    StructuralChange,
)


class StructuralChangeProducerResult(BaseModel):
    """Typed handoff consumed by Feature 008 and reused by Feature 005.

    Holds draft-eligible ``changes``, suppressed ``no_adr_outcomes``, the immutable
    ``evidence`` supporting both, and free-form ``diagnostics`` strings (never raw
    diffs). All collections are deterministically ordered by their producer.
    """

    model_config = ConfigDict(frozen=True)

    changes: tuple[StructuralChange, ...] = ()
    no_adr_outcomes: tuple[NoAdrOutcome, ...] = ()
    evidence: tuple[ChangeEvidence, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @property
    def draft_eligible_changes(self) -> tuple[StructuralChange, ...]:
        """Changes whose recommendation is ``draft`` (Feature 008 readiness)."""

        return tuple(
            change
            for change in self.changes
            if change.adr_recommendation is ADRRecommendation.DRAFT
        )


@runtime_checkable
class StructuralChangeProducer(Protocol):
    """Port: consume immutable candidate evidence, emit a typed result."""

    def produce(self, candidate: object) -> StructuralChangeProducerResult: ...


__all__ = [
    "StructuralChangeProducerResult",
    "StructuralChangeProducer",
]
