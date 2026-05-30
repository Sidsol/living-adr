"""Slice 012-s01: MCP app bootstrap + stdio startup.

The ``living-adr-mcp`` deployable must build a read-only MCP server over the
official SDK and load feature 002 config at startup, failing fast on invalid
config so the read-only context surface never serves traffic with partial
configuration (US-1, FR-1, FR-2, NFR-2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from living_adr.apps.mcp_context_server.app import (
    SERVER_NAME,
    McpContextServerApp,
    build_server,
)
from living_adr.apps.mcp_context_server.startup import (
    McpContextServerStartup,
    load_startup_config,
)
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


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_build_server_uses_named_read_only_mcp_server() -> None:
    app = build_server()
    assert isinstance(app, McpContextServerApp)
    assert app.server.name == SERVER_NAME
    # stdio is the only PoC transport; the SDK server is the wrapped boundary.
    assert app.server.instructions is not None


def test_build_server_registers_no_tools_until_later_slices() -> None:
    app = build_server()
    assert app.tool_names == ()


def test_load_startup_config_reads_valid_config(tmp_path: Path) -> None:
    startup = load_startup_config(_write(tmp_path, VALID_YAML))
    assert isinstance(startup, McpContextServerStartup)
    assert startup.ready is True
    assert startup.config.repositories[0].identity.repo == "example-repo"


def test_load_startup_config_fails_fast_on_invalid_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigStartupError):
        load_startup_config(_write(tmp_path, INVALID_YAML))
