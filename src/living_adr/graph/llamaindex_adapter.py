"""Default LivingADR graph adapter backed by a LlamaIndex property graph.

``LlamaIndexPropertyGraphAdapter`` implements feature 006's
:class:`~living_adr.core.graph.ports.ArchitectureGraphStore` (write) and
:class:`~living_adr.core.graph.ports.ArchitectureContextQuery` (read) ports on a
single object, keeping every LlamaIndex detail (``SimplePropertyGraphStore``,
``EntityNode``, ``Relation``) strictly behind the boundary. Public methods accept
and return only LivingADR domain values plus standard scalars/collections, so the
graph backend stays swappable (architecture #service-boundaries).

The adapter is built up across slices:

* **Slice 1** — persistence root, initialize/reopen, no-leak boundary.
* **Slice 2** — repository isolation + schema metadata.
* **Slice 3/4** — provenance, validated mapping, write-side port methods.
* **Slice 5** — read snapshots + query DTOs.
* **Slice 7** — drift diagnostics (``check_conformance``).
"""

from __future__ import annotations

import json

from living_adr.core.graph.models import SchemaVersion, utc_now
from living_adr.core.repository import RepositoryIdentity
from living_adr.graph.persistence import (
    GraphPersistenceConfig,
    ensure_storage_dir,
    graph_meta_path,
    property_graph_path,
)
from living_adr.graph.schema import (
    ADAPTER_NAME,
    ADAPTER_SCHEMA_VERSION,
    SchemaMetadataError,
    UnsupportedSchemaVersionError,
    is_supported,
)


def _lazy_simple_property_graph_store():
    """Import the LlamaIndex store lazily so import cost is paid on first use."""

    from llama_index.core.graph_stores import SimplePropertyGraphStore

    return SimplePropertyGraphStore


class LlamaIndexPropertyGraphAdapter:
    """Repository-scoped property-graph adapter behind feature 006 ports."""

    def __init__(self, config: GraphPersistenceConfig | None = None) -> None:
        self._config = config or GraphPersistenceConfig()
        # Private per-repository caches; never exposed publicly (no-leak rule).
        self._stores: dict[str, object] = {}
        self._meta: dict[str, dict] = {}
        #: Public counter so the conformance suite can assert that a rejected
        #: approval performed zero adapter writes.
        self.write_calls = 0

    # ------------------------------------------------------------ persistence
    def _store_cache_key(self, repository: RepositoryIdentity) -> str:
        return f"{repository.key}#{repository.repo_id}"

    def _open_store(self, repository: RepositoryIdentity):
        """Return the cached/loaded ``SimplePropertyGraphStore`` for a repo."""

        cache_key = self._store_cache_key(repository)
        if cache_key in self._stores:
            return self._stores[cache_key]
        store_cls = _lazy_simple_property_graph_store()
        path = property_graph_path(self._config, repository)
        if path.exists():
            store = store_cls.from_persist_path(str(path))
        else:
            store = store_cls()
        self._stores[cache_key] = store
        return store

    def _persist_store(self, repository: RepositoryIdentity) -> None:
        store = self._open_store(repository)
        ensure_storage_dir(self._config, repository)
        store.persist(str(property_graph_path(self._config, repository)))

    # --------------------------------------------------------------- metadata
    def _meta_default(self, repository: RepositoryIdentity) -> dict:
        now = utc_now().isoformat()
        return {
            "repository_key": repository.key,
            "repo_id": repository.repo_id,
            "adapter_name": ADAPTER_NAME,
            "schema_version": {
                "major": ADAPTER_SCHEMA_VERSION.major,
                "minor": ADAPTER_SCHEMA_VERSION.minor,
            },
            "revision": 0,
            "created_at": now,
            "updated_at": now,
        }

    def _read_meta(self, repository: RepositoryIdentity) -> dict | None:
        cache_key = self._store_cache_key(repository)
        if cache_key in self._meta:
            return self._meta[cache_key]
        path = graph_meta_path(self._config, repository)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        self._meta[cache_key] = data
        return data

    def _write_meta(self, repository: RepositoryIdentity, meta: dict) -> None:
        meta["updated_at"] = utc_now().isoformat()
        ensure_storage_dir(self._config, repository)
        graph_meta_path(self._config, repository).write_text(
            json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8"
        )
        self._meta[self._store_cache_key(repository)] = meta

    @staticmethod
    def _meta_schema_version(meta: dict) -> SchemaVersion:
        raw = meta.get("schema_version")
        if not isinstance(raw, dict) or "major" not in raw or "minor" not in raw:
            raise SchemaMetadataError(
                "graph metadata is missing a well-formed schema_version"
            )
        return SchemaVersion(major=int(raw["major"]), minor=int(raw["minor"]))

    # ----------------------------------------------------- lifecycle (slice 1)
    def initialize_repository(
        self, repository: RepositoryIdentity
    ) -> SchemaVersion:
        """Create an empty, schema-stamped graph for ``repository`` if absent.

        Idempotent: re-initializing an existing repository returns its current
        (persisted) schema version without resetting graph data.
        """

        existing = self._read_meta(repository)
        if existing is not None:
            return self._meta_schema_version(existing)
        ensure_storage_dir(self._config, repository)
        self._persist_store(repository)
        meta = self._meta_default(repository)
        self._write_meta(repository, meta)
        return ADAPTER_SCHEMA_VERSION

    def is_initialized(self, repository: RepositoryIdentity) -> bool:
        return graph_meta_path(self._config, repository).exists()

    def current_schema_version(
        self, repository: RepositoryIdentity
    ) -> SchemaVersion:
        """Return the persisted schema version, or fail deterministically.

        Raises :class:`SchemaMetadataError` when the repository graph has not
        been initialized, and :class:`UnsupportedSchemaVersionError` when the
        persisted version is outside this adapter's supported range — never a
        silent read of stale structures (US-2).
        """

        meta = self._read_meta(repository)
        if meta is None:
            raise SchemaMetadataError(
                f"no graph metadata for repository {repository.key!r}; "
                "initialize or migrate before querying schema version"
            )
        version = self._meta_schema_version(meta)
        if not is_supported(version):
            raise UnsupportedSchemaVersionError(
                f"persisted schema {version.label} is not supported by adapter "
                f"{ADAPTER_NAME} ({ADAPTER_SCHEMA_VERSION.label})"
            )
        return version


__all__ = ["LlamaIndexPropertyGraphAdapter"]
