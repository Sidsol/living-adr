"""SCM adapter package (feature 003).

Houses GitHub-specific webhook verification, payload filtering, normalization,
and the GitHub provider adapter. Provider-specific GitHub payload traversal is
confined to this package; workflow-facing code consumes only the provider-neutral
core contracts in :mod:`living_adr.core.scm` and :mod:`living_adr.core.ingestion`.
"""
