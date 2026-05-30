"""LivingADR package root.

The console entry point ``living-adr`` (see pyproject ``[project.scripts]``) maps
to :func:`main`, which delegates to the onboarding CLI. The import is lazy so
importing the package never eagerly pulls the CLI/onboarding stack.
"""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point: delegate to the onboarding CLI."""

    from living_adr.cli import main as _cli_main

    return _cli_main(argv)
