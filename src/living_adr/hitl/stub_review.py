"""Accept-only stub HITL review for the walking skeleton.

This is a SMOKE STUB for the production HITL review service. It supports only the
"accept" path and mints an ``ApprovedReviewDecision`` capability that binds the
exact reviewed draft content (SHA-256), reviewer, structural change, and
repository scope. It deliberately rejects mismatched inputs *before* any
persistence so the approval-bound mutation seam stays meaningful even in smoke
(architecture #service-boundaries; FM-20 meaningful approval).

Out of scope (deferred to later features): edit/reject paths, one-shot TTL
consumption, decision versioning, durable capability storage, and review UI.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from living_adr.core.models import (
    ADRDraft,
    ApprovedReviewDecision,
    StructuralChange,
)

# Fixed mint timestamp keeps smoke decisions deterministic.
_SMOKE_MINTED_AT = datetime(2024, 1, 15, 12, 30, 0, tzinfo=UTC)


class ReviewMismatchError(ValueError):
    """Raised when the reviewed draft and change do not agree before approval."""


def _draft_content_hash(draft: ADRDraft) -> str:
    return hashlib.sha256(draft.rendered_markdown.encode("utf-8")).hexdigest()


def accept_draft(
    draft: ADRDraft,
    change: StructuralChange,
    *,
    reviewer_id: str,
) -> ApprovedReviewDecision:
    """Mint an approved decision for a draft, rejecting mismatched inputs.

    Validation guards (must run before any downstream persistence):
    - draft and change must share the same repository scope, and
    - the draft must reference this exact structural change.
    """

    if draft.repository != change.repository:
        raise ReviewMismatchError(
            "Draft and structural change belong to different repositories."
        )
    if draft.structural_change_id != change.change_id:
        raise ReviewMismatchError(
            "Draft does not reference the supplied structural change."
        )

    content_hash = _draft_content_hash(draft)
    decision_id = (
        "decision-"
        + hashlib.sha256(
            f"{draft.draft_id}|{reviewer_id}|{content_hash}".encode()
        ).hexdigest()[:16]
    )
    return ApprovedReviewDecision(
        repository=draft.repository,
        decision_id=decision_id,
        reviewer_id=reviewer_id,
        adr_draft_id=draft.draft_id,
        adr_draft_content_hash=content_hash,
        structural_change_event_id=change.change_id,
        minted_at=_SMOKE_MINTED_AT,
        approved=True,
        is_stub=True,
    )
