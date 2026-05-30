"""Deterministic smoke classifier and ADR draft renderer.

This module is a smoke stub: it turns one ``SCMEvent`` into exactly one
``StructuralChange`` + ``ChangeEvidence`` and renders one provisional ``ADRDraft``.
It performs no Claude / external calls and produces fully deterministic output
(FM-06: rationale is labeled provisional and cites concrete evidence).
"""

from __future__ import annotations

import hashlib

from living_adr.core.models import (
    ADRDraft,
    ChangeEvidence,
    SCMEvent,
    StructuralChange,
)

STUB_LABEL = (
    "_Deterministic SMOKE STUB output — not production-classifier or "
    "model-authored rationale._"
)


def _deterministic_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def classify_structural_change(
    event: SCMEvent,
) -> tuple[StructuralChange, ChangeEvidence]:
    """Emit exactly one dependency-type structural change plus its evidence.

    The smoke classifier looks for the seeded dependency signal (changes to
    ``requirements.txt`` / ``pyproject.toml``). It is intentionally a single
    deterministic rule, not a production classifier.
    """

    evidence_id = _deterministic_id(
        "evid", event.repository.key, event.delivery_id, str(event.pr_number)
    )
    evidence = ChangeEvidence(
        repository=event.repository,
        evidence_id=evidence_id,
        source_delivery_id=event.delivery_id,
        pr_number=event.pr_number,
        diff_summary=event.diff_summary,
        changed_files=event.changed_files,
    )

    change_id = _deterministic_id(
        "chg", event.repository.key, evidence_id, "dependency"
    )
    change = StructuralChange(
        repository=event.repository,
        change_id=change_id,
        change_type="dependency",
        summary=(
            f"PR #{event.pr_number} introduces a dependency change: "
            f"{event.pr_title}"
        ),
        evidence_id=evidence_id,
    )
    return change, evidence


def render_draft_markdown(
    change: StructuralChange,
    evidence: ChangeEvidence,
    *,
    title: str,
    context: str,
    decision: str,
    consequences: str,
    alternatives: str,
) -> str:
    """Render the provisional ADR as Markdown with an explicit stub label."""

    return "\n".join(
        [
            f"# ADR (DRAFT): {title}",
            "",
            STUB_LABEL,
            "",
            "## Status",
            "Proposed (provisional — pending HITL approval)",
            "",
            "## Context",
            context,
            "",
            "## Decision",
            decision,
            "",
            "## Consequences",
            consequences,
            "",
            "## Alternatives Considered",
            alternatives,
            "",
            "## Evidence Citations",
            f"- evidence:{evidence.evidence_id} (PR #{evidence.pr_number})",
            f"- structural-change:{change.change_id}",
        ]
    )


def draft_adr(change: StructuralChange, evidence: ChangeEvidence) -> ADRDraft:
    """Create one provisional, evidence-citing, stub-labeled ``ADRDraft``."""

    title = f"Adopt dependency change from PR #{evidence.pr_number}"
    context = (
        "A merged PR introduced a dependency change classified as "
        f"architecture-significant. Evidence: {evidence.diff_summary}"
    )
    decision = (
        "Record the dependency change as an architecturally significant "
        "decision so future readers understand why it was adopted."
    )
    consequences = (
        "The new dependency becomes part of the supported surface; future "
        "changes must consider its maintenance and security posture."
    )
    alternatives = (
        "PLACEHOLDER (smoke): alternatives such as avoiding the dependency or "
        "using a standard-library equivalent were not evaluated by this stub."
    )
    rendered = render_draft_markdown(
        change,
        evidence,
        title=title,
        context=context,
        decision=decision,
        consequences=consequences,
        alternatives=alternatives,
    )
    draft_id = _deterministic_id(
        "draft", change.repository.key, change.change_id, evidence.evidence_id
    )
    return ADRDraft(
        repository=change.repository,
        draft_id=draft_id,
        structural_change_id=change.change_id,
        status="proposed",
        title=title,
        context=context,
        decision=decision,
        consequences=consequences,
        alternatives=alternatives,
        citations=(evidence.evidence_id,),
        rendered_markdown=rendered,
        is_stub=True,
    )
