"""SQLite-backed LangGraph checkpointer factory (feature 015, slice 2).

Owns durable in-flight workflow state for the workflow-service. SQLite-specific
details (connection setup, WAL journaling, busy timeout, the LangGraph
``SqliteSaver``) are isolated behind this factory so a post-PoC migration stays
localized (NFR-5). The workflow-service is the **sole writer**; readers (MCP, the
graph adapter) never receive write access to this database (US-2;
architecture #data-model single-writer/WAL).

WAL mode + a short ``busy_timeout`` let the single writer and any short-lived
reads coexist without a server, and survive process restarts: a fresh
checkpointer opened on the same path reloads persisted thread state (FR-5;
NFR-1).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, ConfigDict, field_validator

#: Default location for workflow-service-owned durable state. Relative so it sits
#: under the service's working tree; operators may override via config.
DEFAULT_CHECKPOINT_PATH = Path("var") / "workflow_service" / "state" / (
    "workflow_checkpoints.db"
)

#: Modules whose pydantic/dataclass values are persisted into checkpoints. Added
#: to the msgpack allowlist so deserialization is explicit and future-proof
#: (avoids the "unregistered type" deprecation on reload).
_ALLOWED_STATE_MODULES: tuple[tuple[str, ...], ...] = (
    ("living_adr.workflow.state",),
    ("living_adr.core.models",),
    ("living_adr.core.approval",),
    ("living_adr.core.adr",),
    ("living_adr.core.graph.models",),
)


class WorkflowCheckpointConfig(BaseModel):
    """Configuration for the workflow checkpoint database (no secrets)."""

    model_config = ConfigDict(frozen=True)

    db_path: Path = DEFAULT_CHECKPOINT_PATH
    busy_timeout_ms: int = 5000
    journal_mode: str = "WAL"

    @field_validator("busy_timeout_ms")
    @classmethod
    def _positive_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("busy_timeout_ms must be positive")
        return value


def create_connection(config: WorkflowCheckpointConfig) -> sqlite3.Connection:
    """Open a configured SQLite connection, creating parent directories.

    Applies WAL journaling and a busy timeout so the single writer tolerates
    brief lock contention. ``check_same_thread=False`` lets the checkpointer be
    used from the workflow-service request/worker threads (the service remains
    the only writer).
    """

    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(config.db_path), check_same_thread=False)
    connection.execute(f"PRAGMA journal_mode={config.journal_mode}")
    connection.execute(f"PRAGMA busy_timeout={config.busy_timeout_ms}")
    return connection


class WorkflowCheckpointer:
    """Owns the SQLite connection + ``SqliteSaver`` for the workflow graph.

    Use as a context manager (closes the connection on exit) or hold it for the
    service lifetime and call :meth:`close` at shutdown. ``saver`` is the
    allowlist-configured LangGraph checkpointer passed to ``graph.compile``.
    """

    def __init__(self, config: WorkflowCheckpointConfig | None = None) -> None:
        self.config = config or WorkflowCheckpointConfig()
        self.connection = create_connection(self.config)
        base_saver = SqliteSaver(self.connection)
        base_saver.setup()
        # Shallow clone with an explicit msgpack allowlist for our state modules.
        self.saver = base_saver.with_allowlist(_ALLOWED_STATE_MODULES)

    def journal_mode(self) -> str:
        """Return the active SQLite journal mode (e.g. ``"wal"``)."""

        row = self.connection.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]) if row else ""

    def busy_timeout(self) -> int:
        """Return the configured busy timeout in milliseconds."""

        row = self.connection.execute("PRAGMA busy_timeout").fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> WorkflowCheckpointer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def create_checkpointer(
    config: WorkflowCheckpointConfig | None = None,
) -> WorkflowCheckpointer:
    """Build a configured :class:`WorkflowCheckpointer` (WAL + setup applied)."""

    return WorkflowCheckpointer(config)


__all__ = [
    "DEFAULT_CHECKPOINT_PATH",
    "WorkflowCheckpointConfig",
    "WorkflowCheckpointer",
    "create_connection",
    "create_checkpointer",
]
