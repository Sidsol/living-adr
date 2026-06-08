"""workflow-service startup config loading (feature 002).

Loads and validates the LivingADR configuration before the workflow service
becomes ready. Invalid config fails the process at startup rather than allowing
webhook ingestion or LangGraph orchestration to run against partial config.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from living_adr.apps.startup_base import ConfigStartupBase

if TYPE_CHECKING:
    from collections.abc import Mapping

    from living_adr.core.config import LivingADRConfig
    from living_adr.scm.github_provider import GitHubProvider

WEBHOOK_SECRET_ENV = "GITHUB_WEBHOOK_SECRET"
STORAGE_PATH_ENV = "LIVING_ADR_STORAGE_PATH"
APP_ID_ENV = "GITHUB_APP_ID"
APP_PRIVATE_KEY_PATH_ENV = "GITHUB_APP_PRIVATE_KEY_PATH"
UI_TOKEN_ENV = "LIVING_ADR_UI_TOKEN"
HOST_ENV = "LIVING_ADR_HOST"
PORT_ENV = "LIVING_ADR_PORT"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class WorkflowServiceStartup(ConfigStartupBase):
    """Validated config snapshot owned by the workflow-service entrypoint."""


def build_ingestion_provider(
    config: LivingADRConfig,
    env: Mapping[str, str] | None = None,
) -> GitHubProvider | None:
    """Build a GitHub App provider from env + config, or ``None`` when absent.

    The receiver still starts without App credentials (provider-less
    receive -> verify -> filter -> persist). When both ``GITHUB_APP_ID`` and
    ``GITHUB_APP_PRIVATE_KEY_PATH`` are set, a GitHub App-authenticated provider
    is wired so accepted merged PRs fetch real evidence. The installation id is
    taken from the configured (single-repo PoC) repository. No network call is
    made here — installation tokens are minted lazily on the first fetch.
    """

    resolved = os.environ if env is None else env
    app_id = (resolved.get(APP_ID_ENV) or "").strip()
    key_path = (resolved.get(APP_PRIVATE_KEY_PATH_ENV) or "").strip()
    if not app_id or not key_path:
        return None

    from living_adr.scm.github_app_client import GitHubAppClient
    from living_adr.scm.github_provider import GitHubProvider

    installation_id = config.repositories[0].github_app_installation_id
    client = GitHubAppClient.from_private_key_file(
        app_id=app_id,
        private_key_path=key_path,
        installation_id=installation_id,
    )
    return GitHubProvider(client)


def main() -> int:  # pragma: no cover - process entrypoint, exercised manually
    """Console entrypoint: fail fast on invalid config/env, then serve webhooks.

    Wires the validated config (feature 002), the durable SQLite ingestion store,
    and the verified-request :class:`IngestionPipeline` behind the HMAC-verifying
    :class:`GitHubWebhookHandler`, then serves the receiver over HTTP via uvicorn.
    A GitHub App provider is wired when ``GITHUB_APP_ID`` +
    ``GITHUB_APP_PRIVATE_KEY_PATH`` are set (accepted merged PRs then fetch real
    evidence); otherwise the pipeline stays provider-less (receive -> verify ->
    filter -> persist). Config + env are read once; restart to apply changes.
    """

    import uvicorn

    from living_adr.apps.workflow_service.asgi import create_webhook_app
    from living_adr.apps.workflow_service.drafting_runner import (
        build_drafting_runtime_from_env,
    )
    from living_adr.apps.workflow_service.hitl_routes import create_hitl_app
    from living_adr.apps.workflow_service.observability import (
        build_observability_for_app,
    )
    from living_adr.apps.workflow_service.webhooks import GitHubWebhookHandler
    from living_adr.persistence.ingestion_store import SqliteIngestionStore
    from living_adr.workflow.ingestion import IngestionPipeline

    startup = WorkflowServiceStartup.from_path()

    secret = os.environ.get(WEBHOOK_SECRET_ENV, "")
    if not secret.strip():
        raise SystemExit(
            f"{WEBHOOK_SECRET_ENV} is required to start the workflow service "
            "(it verifies inbound GitHub webhook signatures)."
        )

    observability = build_observability_for_app()

    storage_dir = Path(os.environ.get(STORAGE_PATH_ENV, "."))
    storage_dir.mkdir(parents=True, exist_ok=True)
    store = SqliteIngestionStore(storage_dir / "ingestion.db")

    provider = build_ingestion_provider(startup.config)
    pipeline = IngestionPipeline(
        config=startup.config,
        store=store,
        provider=provider,
        observability=observability,
    )
    handler = GitHubWebhookHandler(
        secret=secret,
        pipeline=pipeline,
        observability=observability,
    )
    runtime = build_drafting_runtime_from_env(
        config=startup.config,
        storage_dir=storage_dir,
        observability=observability,
    )
    draft_scheduler = runtime.scheduler if runtime is not None else None
    hitl_app = None
    if runtime is not None:
        ui_token = os.environ.get(UI_TOKEN_ENV)
        hitl_app = create_hitl_app(
            gateway=runtime.gateway,
            ui_token=ui_token,
            nonce_secret=ui_token or "dev-nonce-secret",
            observability=observability,
        )
    app = create_webhook_app(
        handler=handler, draft_scheduler=draft_scheduler, hitl_app=hitl_app
    )

    host = os.environ.get(HOST_ENV, DEFAULT_HOST)
    port = int(os.environ.get(PORT_ENV, str(DEFAULT_PORT)))
    uvicorn.run(app, host=host, port=port)
    return 0
