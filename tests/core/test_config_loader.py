"""Slice 2: YAML config loader + startup path resolution diagnostics."""

from __future__ import annotations

from pathlib import Path

import pytest

from living_adr.core.config import LivingADRConfig
from living_adr.core.config_loader import (
    CONFIG_ENV_VAR,
    DEFAULT_CONFIG_FILENAME,
    ConfigStartupError,
    load_living_adr_config,
    resolve_config_path,
)

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


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_resolve_uses_default_when_env_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    resolved = resolve_config_path()
    assert resolved == (tmp_path / DEFAULT_CONFIG_FILENAME)


def test_resolve_uses_env_override_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alt = tmp_path / "custom.yaml"
    monkeypatch.setenv(CONFIG_ENV_VAR, str(alt))
    assert resolve_config_path() == alt


def test_explicit_path_beats_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CONFIG_ENV_VAR, str(tmp_path / "env.yaml"))
    explicit = tmp_path / "explicit.yaml"
    assert resolve_config_path(explicit) == explicit


def test_load_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / DEFAULT_CONFIG_FILENAME, VALID_YAML)
    config = load_living_adr_config()
    assert isinstance(config, LivingADRConfig)
    assert config.repositories[0].identity.repo == "example-repo"


def test_load_env_override_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alt = _write(tmp_path / "elsewhere.yaml", VALID_YAML)
    monkeypatch.setenv(CONFIG_ENV_VAR, str(alt))
    config = load_living_adr_config()
    assert config.repositories[0].canonical_key == (
        "github.com/example-org/example-repo"
    )


def test_missing_file_raises_startup_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigStartupError) as exc:
        load_living_adr_config(tmp_path / "does-not-exist.yaml")
    assert "not found" in str(exc.value).lower()


def test_invalid_yaml_raises_startup_error(tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad.yaml", "repositories: [unclosed\n  - : :")
    with pytest.raises(ConfigStartupError) as exc:
        load_living_adr_config(bad)
    assert "yaml" in str(exc.value).lower() or "parse" in str(exc.value).lower()


def test_non_mapping_top_level_raises_startup_error(tmp_path: Path) -> None:
    bad = _write(tmp_path / "list.yaml", "- just\n- a\n- list\n")
    with pytest.raises(ConfigStartupError):
        load_living_adr_config(bad)


def test_empty_repositories_raises_startup_error_with_field(tmp_path: Path) -> None:
    bad = _write(tmp_path / "empty.yaml", "repositories: []\n")
    with pytest.raises(ConfigStartupError) as exc:
        load_living_adr_config(bad)
    assert "repositories" in str(exc.value).lower()


def test_validation_error_surfaces_field_diagnostics(tmp_path: Path) -> None:
    missing_field = VALID_YAML.replace("    external_llm_allowed: false\n", "")
    bad = _write(tmp_path / "missing.yaml", missing_field)
    with pytest.raises(ConfigStartupError) as exc:
        load_living_adr_config(bad)
    assert "external_llm_allowed" in str(exc.value)
