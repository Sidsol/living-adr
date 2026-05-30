"""LivingADR default graph adapter package.

Public surface only: the ``LlamaIndexPropertyGraphAdapter`` and its persistence
configuration. LlamaIndex storage contexts, ``SimplePropertyGraphStore``,
``EntityNode``/``Relation``, and any SQLite handles stay private to the adapter
modules and never appear in this package's exports (architecture
#service-boundaries -- the graph backend must stay swappable).
"""

from living_adr.graph.llamaindex_adapter import LlamaIndexPropertyGraphAdapter
from living_adr.graph.persistence import GraphPersistenceConfig, OpenMode

__all__ = [
    "GraphPersistenceConfig",
    "LlamaIndexPropertyGraphAdapter",
    "OpenMode",
]
