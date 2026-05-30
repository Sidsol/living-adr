"""workflow-service smoke entrypoint.

Exposes a callable ``SmokeWorkflowApp`` that owns event replay for the walking
skeleton. Later features replace this with real webhook receipt + LangGraph
orchestration; this stub only wires the seeded replay path.
"""

from __future__ import annotations

from living_adr.workflow.smoke_fixture import ReplayResult, SmokeEventReplayer


class SmokeWorkflowApp:
    """Minimal workflow-service app owning the smoke replay seam."""

    def __init__(self) -> None:
        self._replayer = SmokeEventReplayer()

    def replay_smoke_event(self) -> ReplayResult:
        """Replay the seeded merged-PR-like event once, reporting duplicates."""

        return self._replayer.replay()
