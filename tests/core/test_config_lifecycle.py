"""Slice 4: restart-required lifecycle semantics.

Config is read once at startup and snapshotted. There is no hot reload, no file
watcher, no background reload task, and no per-request re-parse. Changing tracked
repositories requires restarting both deployables.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import living_adr.apps.startup_base as startup_base_mod
import living_adr.core.config_loader as loader_mod
from living_adr.apps.workflow_service.startup import WorkflowServiceStartup
from living_adr.core.config_loader import load_living_adr_config

REPO_ROOT = Path(__file__).resolve().parents[2]

CONFIG_A = """
repositories:
  - identity:
      host: github.com
      owner: example-org
      repo: repo-a
      repo_id: "1"
    github_app_installation_id: "11"
    default_branch: main
    adr_publication_policy: livingadr_only
    external_llm_allowed: false
"""

CONFIG_B = """
repositories:
  - identity:
      host: github.com
      owner: example-org
      repo: repo-b
      repo_id: "2"
    github_app_installation_id: "22"
    default_branch: main
    adr_publication_policy: livingadr_only
    external_llm_allowed: false
"""


def test_startup_snapshot_does_not_hot_reload_after_file_change(
    tmp_path: Path,
) -> None:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(CONFIG_A, encoding="utf-8")

    startup = WorkflowServiceStartup.from_path(path)
    assert startup.config.repositories[0].identity.repo == "repo-a"

    # Mutate the file after startup; the in-memory snapshot must NOT change.
    path.write_text(CONFIG_B, encoding="utf-8")
    assert startup.config.repositories[0].identity.repo == "repo-a"


def test_explicit_reload_picks_up_changes_simulating_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(CONFIG_A, encoding="utf-8")
    first = load_living_adr_config(path)
    assert first.repositories[0].identity.repo == "repo-a"

    path.write_text(CONFIG_B, encoding="utf-8")
    # Only an explicit reload (i.e. a process restart) observes new content.
    second = load_living_adr_config(path)
    assert second.repositories[0].identity.repo == "repo-b"


def test_loaded_config_snapshot_is_immutable(tmp_path: Path) -> None:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(CONFIG_A, encoding="utf-8")
    config = load_living_adr_config(path)
    with pytest.raises(Exception):  # noqa: B017 - frozen model rejects mutation
        config.repositories[0].identity.repo = "mutated"  # type: ignore[misc]


def test_no_hot_reload_machinery_in_source() -> None:
    sources = (
        inspect.getsource(loader_mod) + inspect.getsource(startup_base_mod)
    ).lower()
    forbidden_markers = [
        "watchdog",
        "filewatch",
        "create_task",
        "threading",
        "while true",
    ]
    for forbidden in forbidden_markers:
        assert forbidden not in sources


def test_example_config_validates_against_schema() -> None:
    example = REPO_ROOT / "living-adr.config.example.yaml"
    assert example.exists(), f"missing {example}"
    config = load_living_adr_config(example)
    assert len(config.repositories) >= 1


def test_example_config_documents_restart_required() -> None:
    example = REPO_ROOT / "living-adr.config.example.yaml"
    text = example.read_text(encoding="utf-8").lower()
    assert "restart" in text
    assert "no hot reload" in text or "no hot-reload" in text
