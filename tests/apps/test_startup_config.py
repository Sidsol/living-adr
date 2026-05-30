"""Slice 2: both deployables load validated config at startup and fail fast.

Neither the workflow service nor the MCP context server may become ready while
configuration is missing or invalid (US-1, US-4, FR-9).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from living_adr.apps.mcp_context_server.startup import McpContextServerStartup
from living_adr.apps.workflow_service.startup import WorkflowServiceStartup
from living_adr.core.config_loader import ConfigStartupError

VALID_YAML = """
repositories:
  - identity:
      host: github.com
      owner: example-org
      repo: example-repo
      repo_id: "100200300"
    github_app_installation_id: "12345678"
    default_branch: main
    adr_publication_policy: livingadr_only
    external_llm_allowed: false
"""

INVALID_YAML = "repositories: []\n"

_STARTUP_CLASSES = [WorkflowServiceStartup, McpContextServerStartup]


def _valid(tmp_path: Path) -> Path:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(VALID_YAML, encoding="utf-8")
    return path


def _invalid(tmp_path: Path) -> Path:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(INVALID_YAML, encoding="utf-8")
    return path


@pytest.mark.parametrize("startup_cls", _STARTUP_CLASSES)
def test_startup_loads_valid_config_and_is_ready(
    startup_cls: type, tmp_path: Path
) -> None:
    startup = startup_cls.from_path(_valid(tmp_path))
    assert startup.ready is True
    assert startup.config.repositories[0].identity.repo == "example-repo"


@pytest.mark.parametrize("startup_cls", _STARTUP_CLASSES)
def test_startup_fails_fast_on_invalid_config(
    startup_cls: type, tmp_path: Path
) -> None:
    with pytest.raises(ConfigStartupError):
        startup_cls.from_path(_invalid(tmp_path))


@pytest.mark.parametrize("startup_cls", _STARTUP_CLASSES)
def test_startup_evaluate_reports_not_ready_without_raising(
    startup_cls: type, tmp_path: Path
) -> None:
    result = startup_cls.evaluate(_invalid(tmp_path))
    assert result.ready is False
    assert result.config is None
    assert result.error is not None


@pytest.mark.parametrize("startup_cls", _STARTUP_CLASSES)
def test_startup_evaluate_reports_ready_on_valid(
    startup_cls: type, tmp_path: Path
) -> None:
    result = startup_cls.evaluate(_valid(tmp_path))
    assert result.ready is True
    assert result.config is not None
