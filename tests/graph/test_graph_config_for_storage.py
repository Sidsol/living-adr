"""Phase 6: the shared graph-root helper both deployables resolve from storage."""

from __future__ import annotations

from pathlib import Path

from living_adr.graph.persistence import (
    GRAPH_SUBDIR,
    OpenMode,
    graph_config_for_storage,
)


def test_config_roots_under_storage_graph_subdir() -> None:
    config = graph_config_for_storage(Path("/var/lib/living-adr"))

    assert config.graph_root == Path("/var/lib/living-adr") / GRAPH_SUBDIR
    assert config.open_mode is OpenMode.READ_WRITE


def test_config_accepts_read_only_for_mcp() -> None:
    config = graph_config_for_storage("/data", open_mode=OpenMode.READ_ONLY)

    assert config.graph_root == Path("/data") / GRAPH_SUBDIR
    assert config.open_mode is OpenMode.READ_ONLY
