"""Deterministic merged-PR-like smoke fixture and replay normalization.

This module seeds one repository-scoped merged-PR event and normalizes it into a
single ``SCMEvent``. It also provides ``SmokeEventReplayer`` which tracks provider
delivery ids so duplicate replays are reported deterministically (FM-17:
SCM event duplication/replay). No GitHub or network access is involved.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from living_adr.core.models import RepositoryIdentity, SCMEvent

SMOKE_DELIVERY_ID = "smoke-delivery-0001"

# Fixed timestamp keeps the fixture fully deterministic across runs.
_SMOKE_MERGED_AT = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)


def smoke_repository() -> RepositoryIdentity:
    """The single repository scope used throughout the walking skeleton."""

    return RepositoryIdentity(
        host="github.com",
        owner="living-adr",
        repo="walking-skeleton",
        repo_id="smoke-repo-id-0001",
    )


def merged_pr_fixture() -> dict:
    """Seeded raw merged-PR-like payload (provider-shaped, smoke only)."""

    return {
        "delivery_id": SMOKE_DELIVERY_ID,
        "provider": "github_smoke",
        "action": "closed",
        "merged": True,
        "pull_request": {
            "number": 42,
            "title": "Add httpx dependency for outbound API client",
            "merged_at": _SMOKE_MERGED_AT.isoformat(),
            "changed_files": [
                "pyproject.toml",
                "requirements.txt",
                "src/app/client.py",
            ],
            "diff_summary": (
                "Added new dependency 'httpx>=0.27' to requirements.txt and "
                "pyproject.toml; introduced src/app/client.py using httpx."
            ),
        },
    }


def normalize_to_scm_event(raw: dict) -> SCMEvent:
    """Normalize a raw merged-PR-like payload into one repository-scoped event."""

    pr = raw["pull_request"]
    return SCMEvent(
        repository=smoke_repository(),
        delivery_id=raw["delivery_id"],
        provider=raw["provider"],
        event_type="merged_pr",
        pr_number=pr["number"],
        pr_title=pr["title"],
        merged_at=datetime.fromisoformat(pr["merged_at"]),
        diff_summary=pr["diff_summary"],
        changed_files=tuple(pr["changed_files"]),
    )


class ReplayResult(BaseModel):
    """Outcome of a single smoke replay: the event plus a duplicate flag."""

    model_config = {"frozen": True}

    event: SCMEvent
    is_duplicate: bool


class SmokeEventReplayer:
    """Replays the seeded smoke event, tracking delivery ids for idempotency.

    This is a smoke stub for the production replayable event inbox (FM-01/FM-17).
    It is intentionally in-memory and single-process.
    """

    def __init__(self) -> None:
        self._seen_delivery_ids: set[str] = set()

    def replay(self) -> ReplayResult:
        event = normalize_to_scm_event(merged_pr_fixture())
        is_duplicate = event.delivery_id in self._seen_delivery_ids
        self._seen_delivery_ids.add(event.delivery_id)
        return ReplayResult(event=event, is_duplicate=is_duplicate)
