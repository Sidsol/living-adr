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

from living_adr.core.adr import ADRRecord
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.models import (
    ADRPath,
    ADRRef,
    GraphEdge,
    GraphSnapshotRef,
    MigrationResult,
    NodeId,
    ProvenancedADR,
    RelationshipType,
    SchemaVersion,
    WhyAnswer,
    utc_now,
)
from living_adr.core.models import StructuralChange
from living_adr.core.repository import RepositoryIdentity
from living_adr.graph.llamaindex_mapping import (
    ADR_ID_KEY,
    NODE_KIND_KEY,
    SCOPE_KEY_PROP,
    STATUS_KEY,
    TITLE_KEY,
    adr_node_value,
    adr_to_entity_node,
    edge_to_relation,
    structural_change_node_value,
    structural_change_to_entity_node,
)
from living_adr.graph.persistence import (
    GraphPersistenceConfig,
    ensure_storage_dir,
    graph_meta_path,
    property_graph_path,
)
from living_adr.graph.provenance import (
    PROV_EVIDENCE_ID,
    PROV_SOURCE_ADR_ID,
    EntityProvenance,
    ExtractionMethod,
    provenance_from_properties,
    scope_key,
)
from living_adr.graph.schema import (
    ADAPTER_NAME,
    ADAPTER_SCHEMA_VERSION,
    ENTITY_LABEL_ADR,
    SchemaMetadataError,
    UnsupportedSchemaVersionError,
    is_supported,
)
from living_adr.graph.snapshots import (
    SnapshotState,
    snapshot_state,
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

    def migrate_schema(
        self,
        repository: RepositoryIdentity,
        target_version: SchemaVersion,
        decision: object,
    ) -> MigrationResult:
        """Apply the schema-version governance hook for a repository graph.

        This is the write-side migration hook required by feature 006's
        ``ArchitectureGraphStore`` port. Approval enforcement happens upstream in
        ``ApprovalBoundMutationService``; here we record the version transition
        and persist it. An uninitialized repository is initialized first so the
        transition has a well-defined ``from_version``.
        """

        meta = self._read_meta(repository)
        if meta is None:
            self.initialize_repository(repository)
            meta = dict(self._read_meta(repository) or self._meta_default(repository))
        else:
            meta = dict(meta)
        from_version = self._meta_schema_version(meta)
        meta["schema_version"] = {
            "major": target_version.major,
            "minor": target_version.minor,
        }
        meta["revision"] = int(meta.get("revision", 0)) + 1
        self._write_meta(repository, meta)
        return MigrationResult(
            repository=repository,
            from_version=from_version,
            to_version=target_version,
            applied=True,
        )

    # ----------------------------------------------------- write side (slice 4)
    def _ensure_meta(self, repository: RepositoryIdentity) -> dict:
        meta = self._read_meta(repository)
        if meta is None:
            self.initialize_repository(repository)
            meta = self._read_meta(repository)
        assert meta is not None  # initialize always writes meta
        return meta

    def _write_version(self, repository: RepositoryIdentity) -> SchemaVersion:
        """Schema version recorded on freshly written provenance.

        Uses the adapter's supported version so all new projections are stamped
        consistently even if a repository's metadata was migrated forward.
        """

        return ADAPTER_SCHEMA_VERSION

    def _commit_write(self, repository: RepositoryIdentity) -> None:
        """Persist the in-memory store and bump the repository revision once.

        All validation/mapping happens *before* this is called, so a write that
        fails never reaches this method and never mutates persisted state
        (NFR-2: no partially-current projection is exposed).
        """

        meta = dict(self._ensure_meta(repository))
        meta["revision"] = int(meta.get("revision", 0)) + 1
        self._persist_store(repository)
        self._write_meta(repository, meta)
        self.write_calls += 1

    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision,
    ) -> NodeId:
        if adr.repository != repository:
            raise ValueError(
                "ADR record repository scope does not match the write scope"
            )
        self._ensure_meta(repository)
        provenance = EntityProvenance(
            repository=repository,
            source_adr_id=adr.adr_id,
            decision_id=adr.decision_id,
            extraction_method=ExtractionMethod.DETERMINISTIC_ADR_PROJECTION,
            extracted_at=utc_now(),
            schema_version=self._write_version(repository),
            evidence_id=adr.evidence_ids[0] if adr.evidence_ids else None,
        )
        node = adr_to_entity_node(repository, adr, provenance)
        self._open_store(repository).upsert_nodes([node])
        self._commit_write(repository)
        return NodeId(repository=repository, value=adr_node_value(adr))

    def add_relationship(
        self,
        repository: RepositoryIdentity,
        from_node: NodeId,
        to_node: NodeId,
        relationship: RelationshipType,
        decision: ApprovedReviewDecision,
    ) -> GraphEdge:
        self._ensure_meta(repository)
        edge = GraphEdge(
            repository=repository,
            from_node=from_node,
            to_node=to_node,
            relationship=relationship,
        )
        provenance = self._edge_provenance(repository, from_node, decision)
        relation = edge_to_relation(edge, provenance)
        self._open_store(repository).upsert_relations([relation])
        self._commit_write(repository)
        return edge

    def record_structural_change(
        self,
        repository: RepositoryIdentity,
        change: StructuralChange,
        linked_adr: NodeId,
        decision: ApprovedReviewDecision,
    ) -> NodeId:
        if change.repository != repository:
            raise ValueError(
                "StructuralChange repository scope does not match the write scope"
            )
        self._ensure_meta(repository)
        provenance = EntityProvenance(
            repository=repository,
            source_adr_id=linked_adr.value,
            decision_id=decision.decision_id,
            extraction_method=ExtractionMethod.STRUCTURAL_CHANGE_PROJECTION,
            extracted_at=utc_now(),
            schema_version=self._write_version(repository),
        )
        change_node = structural_change_to_entity_node(repository, change, provenance)
        change_id = NodeId(
            repository=repository, value=structural_change_node_value(change)
        )
        edge = GraphEdge(
            repository=repository,
            from_node=change_id,
            to_node=linked_adr,
            relationship=RelationshipType.RECORDS_STRUCTURAL_CHANGE,
        )
        relation = edge_to_relation(edge, provenance)
        store = self._open_store(repository)
        store.upsert_nodes([change_node])
        store.upsert_relations([relation])
        self._commit_write(repository)
        return change_id

    def supersede_adr(
        self,
        repository: RepositoryIdentity,
        prior_adr: NodeId,
        superseding_adr: NodeId,
        decision: ApprovedReviewDecision,
        reason: str,
    ) -> GraphEdge:
        self._ensure_meta(repository)
        edge = GraphEdge(
            repository=repository,
            from_node=superseding_adr,
            to_node=prior_adr,
            relationship=RelationshipType.SUPERSEDES,
            reason=reason,
        )
        provenance = self._edge_provenance(repository, superseding_adr, decision)
        self._open_store(repository).upsert_relations(
            [edge_to_relation(edge, provenance)]
        )
        self._commit_write(repository)
        return edge

    def retract_adr(
        self,
        repository: RepositoryIdentity,
        adr: NodeId,
        decision: ApprovedReviewDecision,
        reason: str,
    ) -> GraphEdge:
        self._ensure_meta(repository)
        edge = GraphEdge(
            repository=repository,
            from_node=adr,
            to_node=adr,
            relationship=RelationshipType.RETRACTS,
            reason=reason,
        )
        provenance = self._edge_provenance(repository, adr, decision)
        self._open_store(repository).upsert_relations(
            [edge_to_relation(edge, provenance)]
        )
        self._commit_write(repository)
        return edge

    def _edge_provenance(
        self,
        repository: RepositoryIdentity,
        source_node: NodeId,
        decision: ApprovedReviewDecision,
    ) -> EntityProvenance:
        return EntityProvenance(
            repository=repository,
            source_adr_id=source_node.value,
            decision_id=decision.decision_id,
            extraction_method=ExtractionMethod.DETERMINISTIC_ADR_PROJECTION,
            extracted_at=utc_now(),
            schema_version=self._write_version(repository),
        )

    def rebuild_snapshot(
        self,
        repository: RepositoryIdentity,
        at_revision: int | None = None,
    ) -> GraphSnapshotRef:
        """Return a stable, repository-scoped snapshot reference.

        The snapshot is a *logical* revision marker: MCP reads pass it back to
        ``validate_snapshot_current`` to detect whether they observed the latest
        projection. Schema/provenance metadata are preserved; no ADR record is
        mutated (graph data is a projection, never authority).
        """

        meta = self._ensure_meta(repository)
        version = self._meta_schema_version(meta)
        revision = at_revision if at_revision is not None else int(
            meta.get("revision", 0)
        )
        return GraphSnapshotRef(
            repository=repository,
            snapshot_id=f"rev-{revision}",
            schema_version=version,
            created_at=utc_now(),
        )

    # ------------------------------------------------------ read side (slice 5)
    def _current_revision(self, repository: RepositoryIdentity) -> int:
        meta = self._read_meta(repository)
        return int(meta.get("revision", 0)) if meta else 0

    def _adr_nodes(self, repository: RepositoryIdentity) -> list:
        """Return repository-scoped ADR ``EntityNode`` objects (read-only)."""

        if not graph_meta_path(self._config, repository).exists():
            return []
        store = self._open_store(repository)
        wanted_scope = scope_key(repository)
        nodes = []
        for node in store.get():
            props = getattr(node, "properties", {}) or {}
            if props.get(NODE_KIND_KEY) != ENTITY_LABEL_ADR:
                continue
            if props.get(SCOPE_KEY_PROP) != wanted_scope:
                continue  # defence-in-depth scope filter
            nodes.append(node)
        return nodes

    def _node_to_ref(
        self, repository: RepositoryIdentity, node: object
    ) -> ADRRef:
        props = getattr(node, "properties", {}) or {}
        return ADRRef(
            repository=repository,
            adr_id=str(props.get(ADR_ID_KEY, "")),
            title=str(props.get(TITLE_KEY, "")),
            status=str(props.get(STATUS_KEY, "")),
        )

    @staticmethod
    def _citations(props: dict) -> tuple[str, ...]:
        adr_id = str(props.get(PROV_SOURCE_ADR_ID, "")).strip()
        evidence = str(props.get(PROV_EVIDENCE_ID, "")).strip()
        citations = []
        if adr_id:
            citations.append(f"adr:{adr_id}")
        if evidence:
            citations.append(f"evidence:{evidence}")
        return tuple(citations)

    def _node_to_provenanced(
        self,
        repository: RepositoryIdentity,
        node: object,
        snapshot: GraphSnapshotRef | None = None,
    ) -> ProvenancedADR:
        props = getattr(node, "properties", {}) or {}
        # Validate provenance completeness/scope; raises if a node was persisted
        # without the required lineage (should never happen via the write path).
        provenance_from_properties(repository, props)
        return ProvenancedADR(
            repository=repository,
            adr=self._node_to_ref(repository, node),
            citations=self._citations(props),
            snapshot=snapshot,
        )

    def list_adrs(self, repository: RepositoryIdentity) -> tuple[ADRRef, ...]:
        """Return repository-scoped references to every approved ADR node."""

        return tuple(
            self._node_to_ref(repository, node)
            for node in self._adr_nodes(repository)
        )

    def fetch_adr(
        self, repository: RepositoryIdentity, adr_id: str
    ) -> ProvenancedADR | None:
        """Return a provenanced citation DTO for one ADR, or ``None``."""

        for node in self._adr_nodes(repository):
            props = getattr(node, "properties", {}) or {}
            if str(props.get(ADR_ID_KEY)) == adr_id:
                return self._node_to_provenanced(repository, node)
        return None

    def traverse_from_code_area(
        self,
        repository: RepositoryIdentity,
        code_area_id: str,
        relationship_types: set[RelationshipType] | None = None,
        max_depth: int = 2,
        snapshot: GraphSnapshotRef | None = None,
    ) -> list[ADRPath]:
        """Return approved-ADR traversal paths for a code area (read-only)."""

        nodes = self._adr_nodes(repository)
        if not nodes:
            return []
        adrs = tuple(self._node_to_ref(repository, node) for node in nodes)
        edges = self._scoped_edges(repository, relationship_types)
        return [
            ADRPath(
                repository=repository,
                code_area_id=code_area_id,
                edges=edges,
                adrs=adrs,
            )
        ]

    def _scoped_edges(
        self,
        repository: RepositoryIdentity,
        relationship_types: set[RelationshipType] | None,
    ) -> tuple[GraphEdge, ...]:
        if not graph_meta_path(self._config, repository).exists():
            return ()
        store = self._open_store(repository)
        wanted_scope = scope_key(repository)
        edges: list[GraphEdge] = []
        for _src, relation, _dst in store.get_rel_map(store.get(), depth=1):
            props = getattr(relation, "properties", {}) or {}
            if props.get(SCOPE_KEY_PROP) != wanted_scope:
                continue
            try:
                rel = RelationshipType.from_label(relation.label)
            except Exception:  # noqa: BLE001 - unknown labels are skipped on read
                continue
            if relationship_types is not None and rel not in relationship_types:
                continue
            edges.append(
                GraphEdge(
                    repository=repository,
                    from_node=NodeId(repository=repository, value=relation.source_id),
                    to_node=NodeId(repository=repository, value=relation.target_id),
                    relationship=rel,
                    reason=props.get("reason") or None,
                )
            )
        # Deduplicate (get_rel_map can repeat edges).
        seen: set[tuple] = set()
        unique: list[GraphEdge] = []
        for edge in edges:
            key = (edge.from_node.value, edge.to_node.value, edge.relationship.value)
            if key in seen:
                continue
            seen.add(key)
            unique.append(edge)
        return tuple(unique)

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
        snapshot: GraphSnapshotRef | None = None,
        limit: int = 5,
    ) -> WhyAnswer:
        """Answer a why-question from approved ADR context only (read-only)."""

        nodes = self._adr_nodes(repository)
        if not nodes:
            return WhyAnswer(
                repository=repository,
                question=question,
                answer=(
                    "No approved ADR context is available for this repository."
                ),
                adr_id=None,
                citations=(),
                found=False,
            )
        primary = nodes[0]
        props = getattr(primary, "properties", {}) or {}
        ref = self._node_to_ref(repository, primary)
        provenance = tuple(
            self._node_to_provenanced(repository, node, snapshot)
            for node in nodes[: max(limit, 0)]
        )
        return WhyAnswer(
            repository=repository,
            question=question,
            answer=f"Approved decision {ref.adr_id}: {ref.title}.",
            adr_id=ref.adr_id,
            citations=self._citations(props),
            found=True,
            provenance=provenance,
        )

    def validate_snapshot_current(
        self, repository: RepositoryIdentity, snapshot: GraphSnapshotRef
    ) -> SnapshotState:
        """Return whether ``snapshot`` still matches the latest revision."""

        return snapshot_state(snapshot, self._current_revision(repository))


__all__ = ["LlamaIndexPropertyGraphAdapter"]
