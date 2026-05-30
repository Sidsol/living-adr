"""Evaluation harness package (feature 013, slice 5).

Owns SM-03 (retrieval relevance) and SM-04 (architecture question coverage)
regression signals plus a small drafting quality harness. Evaluation scores are
**regression signals, not proof of correctness** (``architecture.md#anti-patterns``
FM-22): fixtures are versioned and include edge/rejected cases to resist
overfitting.
"""

from __future__ import annotations

__all__: list[str] = []
