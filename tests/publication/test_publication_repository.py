"""Slice S011-02 RED tests: durable publication records + intent reservation.

Exercises both the in-memory and SQLite publication record repositories against
the same contract: reserve creates an intent keyed by ``decision_id``, a same
``decision_id``+fingerprint reserve is idempotent (no duplicate), a same
``decision_id`` with a *different* fingerprint is rejected, finalize updates the
durable outcome, and listing is repository-scoped.
"""

from __future__ import annotations

import pytest

from living_adr.publication.models import (
    PublicationRecord,
    PublicationStatus,
    PublicationTargetMismatchError,
)
from living_adr.publication.repository import (
    InMemoryPublicationRepository,
    SqlitePublicationRepository,
)


def _intent(
    *,
    decision_id: str = "decision-1",
    fingerprint: str = "fp-1",
    repository_key: str = "github.com/acme/living-adr",
    status: PublicationStatus = PublicationStatus.PENDING,
) -> PublicationRecord:
    return PublicationRecord(
        decision_id=decision_id,
        repository_key=repository_key,
        adr_record_id="adr-1",
        content_hash="hash-1",
        fingerprint=fingerprint,
        target_branch="main",
        status=status,
    )


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        return InMemoryPublicationRepository()
    return SqlitePublicationRepository(tmp_path / "publication.db")


def test_reserve_creates_intent_and_get_returns_it(repo) -> None:
    stored = repo.reserve(_intent())
    assert stored.status is PublicationStatus.PENDING
    fetched = repo.get("decision-1")
    assert fetched is not None
    assert fetched.decision_id == "decision-1"
    assert fetched.fingerprint == "fp-1"


def test_reserve_same_decision_and_fingerprint_is_idempotent(repo) -> None:
    repo.reserve(_intent())
    again = repo.reserve(_intent())
    assert again.decision_id == "decision-1"
    assert len(repo.list()) == 1


def test_reserve_same_decision_different_fingerprint_is_rejected(repo) -> None:
    repo.reserve(_intent(fingerprint="fp-1"))
    with pytest.raises(PublicationTargetMismatchError):
        repo.reserve(_intent(fingerprint="fp-2"))


def test_finalize_updates_outcome(repo) -> None:
    repo.reserve(_intent())
    final = repo.finalize(
        _intent(status=PublicationStatus.COMMITTED).model_copy(
            update={
                "target_path": "docs/adr/0001-adopt.md",
                "commit_sha": "sha-abc",
            }
        )
    )
    assert final.status is PublicationStatus.COMMITTED
    fetched = repo.get("decision-1")
    assert fetched is not None
    assert fetched.status is PublicationStatus.COMMITTED
    assert fetched.commit_sha == "sha-abc"
    assert fetched.target_path == "docs/adr/0001-adopt.md"


def test_list_is_repository_scoped(repo) -> None:
    repo.reserve(_intent(decision_id="d-a", repository_key="github.com/acme/a"))
    repo.reserve(_intent(decision_id="d-b", repository_key="github.com/acme/b"))
    only_a = repo.list(repository_key="github.com/acme/a")
    assert len(only_a) == 1
    assert only_a[0].decision_id == "d-a"
    assert len(repo.list()) == 2
