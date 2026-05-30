"""HITL review UI view models, summaries, and edited-draft validation (feature 009).

This module is the pure, framework-free heart of the review UI. It transforms a
feature 015 :class:`~living_adr.workflow.state.ReviewRequestPayload` into a
renderable :class:`ReviewPageModel`, projects metadata-only
:class:`PendingReviewSummary` rows for the pending list, and validates
reviewer-edited Markdown for the approve-after-edit path.

Boundary discipline (architecture #anti-patterns, #service-boundaries):
* It redefines **no** feature 015 graph state — it reuses ``ReviewAction`` and
  reads ``ReviewRequestPayload`` fields verbatim.
* It mints **no** approval capability (feature 010) and performs **no** mutation.
* Summaries are metadata-only: the bounded draft preview body is never copied
  into a list summary, only the page model that actually renders it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from living_adr.core.models import RepositoryIdentity
from living_adr.workflow.state import ReviewAction, ReviewRequestPayload

#: Required section headings for an edited ADR draft (case-insensitive match).
REQUIRED_EDIT_SECTIONS: tuple[str, ...] = (
    "title",
    "status",
    "context",
    "decision",
    "consequences",
)

PROVISIONAL_NOTICE = (
    "This draft is provisional and non-authoritative. Approving here records "
    "your review intent and resumes the workflow; it does not publish an ADR or "
    "mint an approval capability."
)


class ConfidenceBand(Enum):
    """Textual confidence band so color is never the only signal (NFR-1)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def label(self) -> str:
        return {
            ConfidenceBand.HIGH: "High confidence",
            ConfidenceBand.MEDIUM: "Medium confidence",
            ConfidenceBand.LOW: "Low confidence",
        }[self]

    @classmethod
    def from_score(cls, score: float) -> ConfidenceBand:
        if score >= 0.75:
            return cls.HIGH
        if score >= 0.4:
            return cls.MEDIUM
        return cls.LOW


@dataclass(frozen=True)
class ReviewPageModel:
    """Everything the review template needs to render one pending draft."""

    thread_id: str
    repository: RepositoryIdentity
    event_key: str
    draft_id: str
    draft_content_hash: str
    draft_preview: str
    evidence_ids: tuple[str, ...]
    confidence: float
    allowed_actions: tuple[ReviewAction, ...]
    provisional: bool = True
    provisional_notice: str = PROVISIONAL_NOTICE

    @property
    def repository_key(self) -> str:
        return self.repository.key

    @property
    def confidence_band(self) -> ConfidenceBand:
        return ConfidenceBand.from_score(self.confidence)

    @property
    def confidence_percent(self) -> int:
        return round(self.confidence * 100)

    @property
    def allowed_action_values(self) -> tuple[str, ...]:
        return tuple(action.value for action in self.allowed_actions)


@dataclass(frozen=True)
class PendingReviewSummary:
    """Metadata-only row for the pending-review list (no draft body)."""

    thread_id: str
    repository_key: str
    draft_id: str
    draft_content_hash: str
    evidence_count: int
    confidence: float

    @property
    def confidence_band(self) -> ConfidenceBand:
        return ConfidenceBand.from_score(self.confidence)


@dataclass(frozen=True)
class ReviewFormError:
    """A single validation error linked to a form control for a11y (NFR-1)."""

    field: str
    message: str


@dataclass(frozen=True)
class EditedDraftValidationResult:
    """Result of validating reviewer-edited Markdown; preserves input on failure."""

    ok: bool
    normalized_content: str
    errors: tuple[ReviewFormError, ...] = field(default_factory=tuple)


def page_model_from_payload(
    payload: ReviewRequestPayload, *, thread_id: str
) -> ReviewPageModel:
    """Project a feature 015 payload into a renderable page model (read-only)."""

    return ReviewPageModel(
        thread_id=thread_id,
        repository=payload.repository,
        event_key=payload.normalized_event_key,
        draft_id=payload.draft_id,
        draft_content_hash=payload.draft_content_hash,
        draft_preview=payload.draft_preview,
        evidence_ids=tuple(payload.evidence_ids),
        confidence=payload.confidence,
        allowed_actions=tuple(payload.allowed_actions),
    )


def pending_summary_from_payload(
    thread_id: str, payload: ReviewRequestPayload
) -> PendingReviewSummary:
    """Project a metadata-only list summary (the preview body is dropped)."""

    return PendingReviewSummary(
        thread_id=thread_id,
        repository_key=payload.repository.key,
        draft_id=payload.draft_id,
        draft_content_hash=payload.draft_content_hash,
        evidence_count=len(payload.evidence_ids),
        confidence=payload.confidence,
    )


def validate_edited_draft(content: str) -> EditedDraftValidationResult:
    """Validate reviewer-edited Markdown, preserving the submitted content.

    Default validation (autopilot-resolved): require non-empty Markdown that
    contains Title, Status, Context, Decision, and Consequences headings. The
    submitted content is always echoed back verbatim so a failed submission never
    discards the reviewer's edits (US-3, FR-6).
    """

    errors: list[ReviewFormError] = []
    if not content.strip():
        errors.append(
            ReviewFormError(
                field="edited_content",
                message="Edited draft must not be empty.",
            )
        )
        return EditedDraftValidationResult(
            ok=False, normalized_content=content, errors=tuple(errors)
        )

    lowered = content.lower()
    missing = [
        section
        for section in REQUIRED_EDIT_SECTIONS
        if section not in lowered
    ]
    for section in missing:
        errors.append(
            ReviewFormError(
                field="edited_content",
                message=(
                    f"Edited draft is missing the required "
                    f"{section.capitalize()} section."
                ),
            )
        )

    return EditedDraftValidationResult(
        ok=not errors,
        normalized_content=content,
        errors=tuple(errors),
    )


__all__ = [
    "REQUIRED_EDIT_SECTIONS",
    "PROVISIONAL_NOTICE",
    "ConfidenceBand",
    "ReviewPageModel",
    "PendingReviewSummary",
    "ReviewFormError",
    "EditedDraftValidationResult",
    "page_model_from_payload",
    "pending_summary_from_payload",
    "validate_edited_draft",
]
