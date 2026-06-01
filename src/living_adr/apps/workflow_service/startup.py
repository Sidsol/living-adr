"""workflow-service startup config loading (feature 002).

Loads and validates the LivingADR configuration before the workflow service
becomes ready. Invalid config fails the process at startup rather than allowing
webhook ingestion or LangGraph orchestration to run against partial config.
"""

from __future__ import annotations

import os
from pathlib import Path

from living_adr.apps.startup_base import ConfigStartupBase

WEBHOOK_SECRET_ENV = "GITHUB_WEBHOOK_SECRET"
STORAGE_PATH_ENV = "LIVING_ADR_STORAGE_PATH"
HOST_ENV = "LIVING_ADR_HOST"
PORT_ENV = "LIVING_ADR_PORT"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class WorkflowServiceStartup(ConfigStartupBase):
    """Validated config snapshot owned by the workflow-service entrypoint."""


def main() -> int:  # pragma: no cover - process entrypoint, exercised manually
    """Console entrypoint: fail fast on invalid config/env, then serve webhooks.

    Wires the validated config (feature 002), the durable SQLite ingestion store,
    and the verified-request :class:`IngestionPipeline` (provider-less: idempotency
    + merged-PR filtering + delivery persistence, no evidence/draft/publish) behind
    the HMAC-verifying :class:`GitHubWebhookHandler`, then serves the receiver over
    HTTP via uvicorn. Config + env are read once; restart to apply changes.
    """

    import uvicorn

    from living_adr.apps.workflow_service.asgi import create_webhook_app
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

    pipeline = IngestionPipeline(
        config=startup.config,
        store=store,
        provider=None,
        observability=observability,
    )
    handler = GitHubWebhookHandler(
        secret=secret,
        pipeline=pipeline,
        observability=observability,
    )
    app = create_webhook_app(handler=handler)

    host = os.environ.get(HOST_ENV, DEFAULT_HOST)
    port = int(os.environ.get(PORT_ENV, str(DEFAULT_PORT)))
    uvicorn.run(app, host=host, port=port)
    return 0
