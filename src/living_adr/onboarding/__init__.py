"""Operator-facing repository onboarding validation (feature 014).

Thin orchestration over the feature 002 config seam and the feature 003 GitHub
provider seam. This package never re-parses YAML, never builds a second GitHub
API client path, and never exports secrets or raw payloads (architecture
#cross-cutting, #anti-patterns).
"""

from __future__ import annotations
