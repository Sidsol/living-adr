"""Static drift + secret-safety test for .env.example (TASK-009/010, FR-8).

Ensures the example file lists every required env var as a placeholder and
contains no real secret material. No runtime/network dependency.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from living_adr.onboarding.required_env import REQUIRED_ENV_VARS, required_env_names

# Repo root: tests/onboarding/test_env_example.py -> parents[2]
_ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def _read_example() -> str:
    assert _ENV_EXAMPLE.exists(), f"missing {_ENV_EXAMPLE}"
    return _ENV_EXAMPLE.read_text(encoding="utf-8")


def test_every_required_env_name_appears_in_example() -> None:
    text = _read_example()
    for name in required_env_names():
        assert f"{name}=" in text, f"{name} missing from .env.example"


def test_example_assigns_placeholders_only_no_real_secrets() -> None:
    text = _read_example()
    forbidden_signatures = (
        "-----BEGIN",
        "PRIVATE KEY",
        "ghp_",
        "ghs_",
        "github_pat_",
        "sk-ant-",
        "lsv2_",
        "whsec_",
    )
    for signature in forbidden_signatures:
        assert signature not in text, f"real-secret signature {signature!r} found"


def test_example_has_comments_for_operator_guidance() -> None:
    text = _read_example()
    assert text.lstrip().startswith("#"), "expected a leading comment header"
    assert "restart" in text.lower()


@pytest.mark.parametrize("var", REQUIRED_ENV_VARS, ids=lambda v: v.name)
def test_each_var_line_uses_its_registered_placeholder(var) -> None:
    text = _read_example()
    assert f"{var.name}={var.placeholder}" in text
