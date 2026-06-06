"""Phase 2: the GitHub provider is wired into the receiver from env + config.

``build_ingestion_provider`` stays provider-less (``None``) without App
credentials, so the receiver still does receive -> verify -> filter -> persist,
and builds a GitHub App-authenticated :class:`GitHubProvider` when
``GITHUB_APP_ID`` + ``GITHUB_APP_PRIVATE_KEY_PATH`` are present. No network call
occurs: the client mints installation tokens lazily on first fetch.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from living_adr.apps.workflow_service.startup import (
    APP_ID_ENV,
    APP_PRIVATE_KEY_PATH_ENV,
    WorkflowServiceStartup,
    build_ingestion_provider,
)
from living_adr.core.config import LivingADRConfig
from living_adr.scm.github_provider import GitHubProvider

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


def _config(tmp_path: Path) -> LivingADRConfig:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(VALID_YAML, encoding="utf-8")
    return WorkflowServiceStartup.from_path(path).config


def _write_pem(tmp_path: Path) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path = tmp_path / "app.pem"
    path.write_bytes(pem)
    return path


def test_returns_none_without_app_credentials(tmp_path: Path) -> None:
    assert build_ingestion_provider(_config(tmp_path), env={}) is None


def test_returns_none_with_partial_credentials(tmp_path: Path) -> None:
    env = {APP_ID_ENV: "123456"}  # private-key path missing
    assert build_ingestion_provider(_config(tmp_path), env=env) is None


def test_builds_github_provider_when_credentials_present(tmp_path: Path) -> None:
    pem = _write_pem(tmp_path)
    env = {APP_ID_ENV: "123456", APP_PRIVATE_KEY_PATH_ENV: str(pem)}

    provider = build_ingestion_provider(_config(tmp_path), env=env)

    assert isinstance(provider, GitHubProvider)
