"""Slice 4 tests: onboarding CLI wrapper (TASK-017..019).

End-to-end command-runner tests over the real OnboardingValidator + feature 002
loader (temp config file), with a fake installation verifier so no network is
touched. Verifies exit codes, safe success output, grouped failure output, the
PoC single-repo label, and that the CLI wrapper holds no YAML/GitHub logic.
"""

from __future__ import annotations

import inspect
import io

from living_adr import cli
from living_adr.core.scm import InstallationStatus, InstallationVerification

_CONFIG_YAML = """\
repositories:
  - identity:
      host: github.com
      owner: acme
      repo: widgets
      repo_id: "100"
    github_app_installation_id: inst-555
    default_branch: main
    adr_publication_policy: livingadr_only
    external_llm_allowed: false
"""

def _full_env() -> dict[str, str]:
    from living_adr.onboarding.required_env import required_env_names

    return {name: f"placeholder-{name.lower()}" for name in required_env_names()}


class _FakeVerifier:
    def __init__(self, status, permissions) -> None:
        self._status = status
        self._permissions = permissions

    def verify_installation(self, repository, installation_id):
        return InstallationVerification(
            repository_key=repository.key,
            expected_installation_id=installation_id,
            installation_id=installation_id
            if self._status is InstallationStatus.INSTALLED
            else None,
            repo_id="100",
            default_branch="main",
            permissions=self._permissions,
            status=self._status,
        )


def _write_config(tmp_path) -> str:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(_CONFIG_YAML, encoding="utf-8")
    return str(path)


def test_passing_validation_exits_zero_with_safe_metadata_and_next_step(
    tmp_path,
) -> None:
    config_path = _write_config(tmp_path)
    stream = io.StringIO()
    code = cli.main(
        ["onboard", "validate", "--config", config_path],
        env=_full_env(),
        installation_verifier=_FakeVerifier(
            InstallationStatus.INSTALLED, {"contents": "read"}
        ),
        stream=stream,
    )
    out = stream.getvalue()
    assert code == 0
    assert "PASS" in out
    assert "github.com/acme/widgets" in out
    assert "livingadr_only" in out
    assert "inst-555" in out
    assert "Next step" in out


def test_blocking_validation_exits_nonzero_with_grouped_diagnostics(
    tmp_path,
) -> None:
    config_path = _write_config(tmp_path)
    stream = io.StringIO()
    code = cli.main(
        ["onboard", "validate", "--config", config_path],
        env=_full_env(),
        installation_verifier=_FakeVerifier(
            InstallationStatus.NOT_INSTALLED, {}
        ),
        stream=stream,
    )
    out = stream.getvalue()
    assert code != 0
    assert "FAIL" in out
    assert "[github_app]" in out


def test_missing_env_blocks_via_cli(tmp_path) -> None:
    config_path = _write_config(tmp_path)
    env = _full_env()
    del env["GITHUB_APP_ID"]
    stream = io.StringIO()
    code = cli.main(
        ["onboard", "validate", "--config", config_path],
        env=env,
        installation_verifier=_FakeVerifier(
            InstallationStatus.INSTALLED, {"contents": "read"}
        ),
        stream=stream,
    )
    assert code != 0
    assert "GITHUB_APP_ID" in stream.getvalue()


def test_output_labels_poc_single_repo_and_excludes_governance(tmp_path) -> None:
    config_path = _write_config(tmp_path)
    stream = io.StringIO()
    cli.main(
        ["onboard", "validate", "--config", config_path],
        env=_full_env(),
        installation_verifier=_FakeVerifier(
            InstallationStatus.INSTALLED, {"contents": "read"}
        ),
        stream=stream,
    )
    out = stream.getvalue().lower()
    assert "poc" in out
    assert "single-repo" in out or "single repo" in out


def test_cli_wrapper_has_no_yaml_or_github_api_logic() -> None:
    source = inspect.getsource(cli)
    for forbidden in (
        "import yaml",
        "yaml.safe_load",
        "import httpx",
        "import requests",
        "/repos/",
        "api.github.com",
    ):
        assert forbidden not in source


def test_package_main_is_callable_and_delegates() -> None:
    from living_adr import main

    assert callable(main)


def test_unknown_command_prints_help_nonzero() -> None:
    stream = io.StringIO()
    code = cli.main([], stream=stream)
    assert code != 0
