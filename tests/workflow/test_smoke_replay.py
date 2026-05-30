"""SL-001 RED tests: deterministic merged-PR replay into one repository-scoped SCMEvent.

These tests assert smoke-depth behavior only: a seeded fixture normalizes into
exactly one repository-scoped ``SCMEvent`` and duplicate delivery ids are handled
deterministically. No GitHub, network, or LLM access is involved.
"""

from __future__ import annotations

from living_adr.apps.workflow_service.main import SmokeWorkflowApp
from living_adr.core.models import RepositoryIdentity, SCMEvent
from living_adr.workflow.smoke_fixture import (
    SMOKE_DELIVERY_ID,
    SmokeEventReplayer,
    merged_pr_fixture,
    normalize_to_scm_event,
    smoke_repository,
)


def test_smoke_repository_is_scoped() -> None:
    repo = smoke_repository()
    assert isinstance(repo, RepositoryIdentity)
    assert repo.key == "github.com/living-adr/walking-skeleton"
    assert repo.repo_id  # opaque provider id is present


def test_normalize_fixture_into_single_scm_event() -> None:
    event = normalize_to_scm_event(merged_pr_fixture())
    assert isinstance(event, SCMEvent)
    assert event.repository == smoke_repository()
    assert event.delivery_id == SMOKE_DELIVERY_ID
    assert event.event_type == "merged_pr"
    assert event.pr_number == 42
    assert event.changed_files  # has at least one changed file
    # Dependency-change signal is preserved for the downstream stub classifier.
    assert "requirements" in event.diff_summary.lower() or any(
        "requirements" in f.lower() or "pyproject" in f.lower()
        for f in event.changed_files
    )


def test_replay_emits_exactly_one_event_first_time() -> None:
    replayer = SmokeEventReplayer()
    result = replayer.replay()
    assert result.is_duplicate is False
    assert isinstance(result.event, SCMEvent)
    assert result.event.delivery_id == SMOKE_DELIVERY_ID


def test_duplicate_replay_is_deterministic_and_idempotent() -> None:
    replayer = SmokeEventReplayer()
    first = replayer.replay()
    second = replayer.replay()
    assert first.is_duplicate is False
    assert second.is_duplicate is True
    # Same normalized event identity both times (deterministic).
    assert second.event.delivery_id == first.event.delivery_id
    assert second.event == first.event


def test_workflow_app_replay_reports_duplicate() -> None:
    app = SmokeWorkflowApp()
    first = app.replay_smoke_event()
    second = app.replay_smoke_event()
    assert first.is_duplicate is False
    assert second.is_duplicate is True
    assert first.event.repository == smoke_repository()
