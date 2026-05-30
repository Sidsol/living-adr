"""SCM adapter package (feature 003).

Houses GitHub-specific webhook verification, payload filtering, normalization,
and the GitHub provider adapter. Provider-specific GitHub payload traversal is
confined to this package; workflow-facing code consumes only the provider-neutral
core contracts in :mod:`living_adr.core.scm` and :mod:`living_adr.core.ingestion`.
"""

from living_adr.scm.github_webhook import (
    FilterDecision,
    FilterResult,
    GitHubPullRequestPayload,
    WebhookHeaders,
    extract_headers,
    normalize_to_scm_event,
    parse_and_filter,
    verify_signature,
)

__all__ = [
    "verify_signature",
    "extract_headers",
    "WebhookHeaders",
    "parse_and_filter",
    "FilterDecision",
    "FilterResult",
    "GitHubPullRequestPayload",
    "normalize_to_scm_event",
]
