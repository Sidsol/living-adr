"""External-LLM allow/deny policy gate (feature 008, slice S-002, US-3).

The gate is evaluated **before** any prompt assembly or Claude egress so that
data from a disallowed repository is never sent to the provider. It reuses
feature 002's :class:`~living_adr.core.config.RepositoryConfig.external_llm_allowed`
and ``LivingADRConfig.allows_external_llm`` (unknown repositories are denied by
default — egress is never inferred for an unconfigured repository).

The decision and its metadata are intentionally small and secret-free: only the
canonical repository key, the boolean outcome, and a stable reason code.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from living_adr.core.config import LivingADRConfig, RepositoryConfig
from living_adr.core.repository import RepositoryIdentity

#: Stable reason codes (metadata-safe; keyed on by observability).
REASON_ALLOWED = "external_llm_allowed"
REASON_DENIED = "external_llm_denied"
REASON_NOT_CONFIGURED = "repository_not_configured"


class PolicyDecision(BaseModel):
    """The outcome of an external-LLM policy evaluation (metadata-safe)."""

    model_config = ConfigDict(frozen=True)

    allowed: bool
    repository_key: str
    reason: str


def evaluate_external_llm_policy(config: RepositoryConfig) -> PolicyDecision:
    """Evaluate the gate for an explicit, known :class:`RepositoryConfig`."""

    allowed = config.external_llm_allowed
    return PolicyDecision(
        allowed=allowed,
        repository_key=config.canonical_key,
        reason=REASON_ALLOWED if allowed else REASON_DENIED,
    )


def evaluate_repository_llm_policy(
    config: LivingADRConfig, repository: RepositoryIdentity
) -> PolicyDecision:
    """Evaluate the gate for a repository looked up in ``LivingADRConfig``.

    An unconfigured repository is denied by default (FM-14, NFR-2): egress is
    never inferred for a repository LivingADR does not track.
    """

    entry = config.get(repository.key)
    if entry is None:
        return PolicyDecision(
            allowed=False,
            repository_key=repository.key,
            reason=REASON_NOT_CONFIGURED,
        )
    return evaluate_external_llm_policy(entry)


def policy_denied_metadata(decision: PolicyDecision) -> dict[str, object]:
    """Safe observability metadata for a policy decision (no secrets)."""

    return {
        "repository_key": decision.repository_key,
        "policy_allowed": decision.allowed,
        "reason": decision.reason,
    }


__all__ = [
    "REASON_ALLOWED",
    "REASON_DENIED",
    "REASON_NOT_CONFIGURED",
    "PolicyDecision",
    "evaluate_external_llm_policy",
    "evaluate_repository_llm_policy",
    "policy_denied_metadata",
]
