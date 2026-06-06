"""Local persistence rules for the LlamaIndex property-graph adapter.

This module owns *where* and *how* repository-scoped graph state lives on disk.
It is deliberately free of any graph behaviour so the path/open-mode policy can be
tested in isolation.

Deployment model (architecture #deployment)
-------------------------------------------
LivingADR's PoC persistence is **same-host, single-writer**. The workflow service
is the only writer; the MCP context server opens read snapshots. Where SQLite
state backs the store, callers are expected to use WAL mode so a single writer and
multiple readers can coexist on one machine. WAL is explicitly a *same-host*
pattern: ``var\\graph`` must never be shared over a network filesystem
(architecture #anti-patterns — "Multi-host WAL assumptions").
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from living_adr.core.repository import RepositoryIdentity

#: Default local graph root, relative to the process working directory. Runtime
#: data written here is *not* committed; tests inject a temp ``graph_root``.
DEFAULT_GRAPH_ROOT: Path = Path("var") / "graph"

_UNSAFE = re.compile(r"[^a-z0-9._-]+")

#: File names within a repository storage directory.
PROPERTY_GRAPH_FILENAME = "property_graph.json"
GRAPH_META_FILENAME = "graph_meta.json"
SNAPSHOTS_DIRNAME = "snapshots"


class OpenMode(Enum):
    """How the adapter intends to use a repository graph.

    ``READ_WRITE`` is the single-writer workflow path; ``READ_ONLY`` is the
    MCP read-snapshot path which must never mutate graph state.
    """

    READ_WRITE = "read_write"
    READ_ONLY = "read_only"


@dataclass(frozen=True)
class GraphPersistenceConfig:
    """Configuration for the adapter's local persistence root and open mode."""

    graph_root: Path = field(default_factory=lambda: DEFAULT_GRAPH_ROOT)
    open_mode: OpenMode = OpenMode.READ_WRITE


#: Sub-directory under the shared storage path that holds the property graph.
GRAPH_SUBDIR = "graph"


def graph_config_for_storage(
    storage_path: Path | str, *, open_mode: OpenMode = OpenMode.READ_WRITE
) -> GraphPersistenceConfig:
    """Graph persistence config rooted at ``<storage_path>/graph``.

    Both deployables derive the property-graph root from the shared
    ``LIVING_ADR_STORAGE_PATH`` so the workflow service (single writer) and the
    read-only MCP context server resolve the **same** per-repository graph.
    """

    return GraphPersistenceConfig(
        graph_root=Path(storage_path) / GRAPH_SUBDIR, open_mode=open_mode
    )


def _repository_slug(repository: RepositoryIdentity) -> str:
    """Derive a filesystem-safe, collision-resistant directory name.

    The name combines a sanitized, lower-cased form of the human-readable key
    with a short hash of ``key|repo_id`` so two repositories that normalize to
    the same slug (or share a key but differ by opaque id) never collide and
    can never escape the graph root.
    """

    raw_key = repository.key
    slug = _UNSAFE.sub("-", raw_key.lower()).strip("-.") or "repo"
    digest = hashlib.sha256(
        f"{raw_key}|{repository.repo_id}".encode()
    ).hexdigest()[:12]
    return f"{slug}-{digest}"


def repository_storage_dir(
    config: GraphPersistenceConfig, repository: RepositoryIdentity
) -> Path:
    """Return the deterministic storage directory for ``repository``.

    The returned path is always a single child directory directly under the
    (resolved) graph root; the sanitized slug guarantees no path-traversal
    component can escape the root.
    """

    root = config.graph_root.resolve()
    target = (root / _repository_slug(repository)).resolve()
    if target.parent != root:
        raise ValueError(
            "derived repository storage path escaped the graph root"
        )
    return target


def ensure_storage_dir(
    config: GraphPersistenceConfig, repository: RepositoryIdentity
) -> Path:
    """Create (if needed) and return the repository storage directory."""

    target = repository_storage_dir(config, repository)
    (target / SNAPSHOTS_DIRNAME).mkdir(parents=True, exist_ok=True)
    return target


def property_graph_path(
    config: GraphPersistenceConfig, repository: RepositoryIdentity
) -> Path:
    return repository_storage_dir(config, repository) / PROPERTY_GRAPH_FILENAME


def graph_meta_path(
    config: GraphPersistenceConfig, repository: RepositoryIdentity
) -> Path:
    return repository_storage_dir(config, repository) / GRAPH_META_FILENAME


__all__ = [
    "DEFAULT_GRAPH_ROOT",
    "GRAPH_META_FILENAME",
    "GraphPersistenceConfig",
    "OpenMode",
    "PROPERTY_GRAPH_FILENAME",
    "SNAPSHOTS_DIRNAME",
    "ensure_storage_dir",
    "graph_meta_path",
    "property_graph_path",
    "repository_storage_dir",
]
