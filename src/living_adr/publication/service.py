"""Approval-bound ADR publish-back orchestration (feature 011).

This slice (S011-01) establishes pure target resolution from
:class:`~living_adr.core.config.RepositoryConfig`. Later slices add approval
authorisation, idempotency, numbering/slugging, the SCM commit, and observability
to the :class:`ADRPublicationService` defined here.

Resolution never hardcodes ``docs/adr``: the directory, padding width, branch,
and template are all derived from configuration, defaulting only when config
leaves them unset (FR-5; architecture #anti-patterns).
"""

from __future__ import annotations

import re

from living_adr.core.config import RepositoryConfig
from living_adr.publication.models import (
    DEFAULT_ADR_PATH_TEMPLATE,
    ADRPublicationTarget,
    adr_directory,
)

_NUMBER_TOKEN = re.compile(r"N+")


def _padding_width(path_template: str) -> int:
    """Width of the zero-padded number token in ``path_template`` (default 4)."""

    match = _NUMBER_TOKEN.search(path_template)
    return len(match.group(0)) if match is not None else 4


def resolve_publication_target(config: RepositoryConfig) -> ADRPublicationTarget:
    """Resolve the repository-scoped publish target from configuration (FR-5).

    Branch resolves to ``adr_target_branch`` when set, else ``default_branch``.
    The path template resolves to ``adr_path_template`` when set, else the
    project default ``docs/adr/NNNN-<slug>.md``. Directory and padding width are
    derived from the resolved template — never hardcoded.
    """

    policy = config.adr_publication_policy
    branch = (config.adr_target_branch or config.default_branch).strip()
    template = (config.adr_path_template or DEFAULT_ADR_PATH_TEMPLATE).strip()
    return ADRPublicationTarget(
        repository_key=config.canonical_key,
        branch=branch,
        path_template=template,
        directory=adr_directory(template),
        padding_width=_padding_width(template),
        publishes_to_github=policy.publishes_to_github,
    )


__all__ = [
    "resolve_publication_target",
]
