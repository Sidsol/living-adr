"""S-002 RED tests: per-repository external-LLM policy gate (feature 008, US-3).

The policy gate must be evaluated **before** any prompt assembly or Claude call.
A denied repository yields a ``llm_policy_denied`` decision with safe metadata and
no provider egress; unknown repositories are denied by default.
"""

from __future__ import annotations

from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.models import RepositoryIdentity
from living_adr.workflow.drafting.policy import (
    PolicyDecision,
    evaluate_external_llm_policy,
    evaluate_repository_llm_policy,
    policy_denied_metadata,
)


def _identity(repo: str = "widgets") -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo=repo, repo_id=f"id-{repo}"
    )


def _config(*, allowed: bool, repo: str = "widgets") -> RepositoryConfig:
    return RepositoryConfig(
        identity=_identity(repo),
        github_app_installation_id="inst-1",
        default_branch="main",
        adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY,
        external_llm_allowed=allowed,
    )


def test_allow_when_external_llm_allowed_true() -> None:
    decision = evaluate_external_llm_policy(_config(allowed=True))
    assert isinstance(decision, PolicyDecision)
    assert decision.allowed is True
    assert decision.repository_key == "github.com/acme/widgets"


def test_deny_when_external_llm_allowed_false() -> None:
    decision = evaluate_external_llm_policy(_config(allowed=False))
    assert decision.allowed is False
    assert decision.reason == "external_llm_denied"


def test_unknown_repository_is_denied_by_default() -> None:
    config = LivingADRConfig(repositories=[_config(allowed=True, repo="known")])
    decision = evaluate_repository_llm_policy(config, _identity("unknown"))
    assert decision.allowed is False
    assert decision.reason == "repository_not_configured"


def test_configured_repository_lookup_allows() -> None:
    config = LivingADRConfig(repositories=[_config(allowed=True, repo="widgets")])
    decision = evaluate_repository_llm_policy(config, _identity("widgets"))
    assert decision.allowed is True


def test_policy_metadata_is_safe() -> None:
    decision = evaluate_external_llm_policy(_config(allowed=False))
    meta = policy_denied_metadata(decision)
    assert meta["repository_key"] == "github.com/acme/widgets"
    assert meta["policy_allowed"] is False
    assert meta["reason"] == "external_llm_denied"
    # No secrets / installation ids / tokens leak through policy metadata.
    serialized = repr(meta).lower()
    assert "inst-1" not in serialized
    assert "token" not in serialized
