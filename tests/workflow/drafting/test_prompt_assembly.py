"""S-004 RED tests: delimited ADR prompt assembly (feature 008, US-1).

The assembler builds a budget-integrated prompt from the Feature 004 structural
change, its evidence summaries, approved-context citations, and an ADR template.
Untrusted repository text is delimited (anti-injection, NFR-4), provisional
labels are present, and raw diff text is never included (only summaries/refs).
"""

from __future__ import annotations

from living_adr.core.models import RepositoryIdentity
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeEvidence,
    ChangeOperation,
    ChangeType,
    EvidenceKind,
    ObservedOperation,
    StructuralChange,
)
from living_adr.workflow.drafting.context import package_architecture_context
from living_adr.workflow.drafting.prompt import (
    UNTRUSTED_DELIMITER_END,
    UNTRUSTED_DELIMITER_START,
    PromptPackage,
    assemble_prompt,
)
from living_adr.workflow.drafting.token_budget import (
    BudgetConfig,
    BudgetStatus,
    HeuristicTokenEstimator,
)


def _repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="widgets", repo_id="r1"
    )


def _change() -> StructuralChange:
    return StructuralChange(
        id="chg-1",
        repository=_repo(),
        source_scm_event_id="evt-1",
        provider_delivery_id="del-1",
        normalized_pr_key="pr-1",
        change_type=ChangeType.DEPENDENCY,
        operation=ChangeOperation.ADDED,
        affected_dependency="requests",
        dependency_ecosystem="python",
        source_paths=("pyproject.toml", "uv.lock"),
        evidence_ids=("ev-1",),
        confidence=0.91,
        reason_code="direct_manifest_add",
        adr_recommendation=ADRRecommendation.DRAFT,
        classifier_name="dependency-change",
        classifier_version="1.0.0",
    )


def _evidence() -> tuple[ChangeEvidence, ...]:
    return (
        ChangeEvidence(
            id="ev-1",
            repository=_repo(),
            source_scm_event_id="evt-1",
            provider_delivery_id="del-1",
            normalized_pr_key="pr-1",
            evidence_kind=EvidenceKind.DEPENDENCY_MANIFEST,
            source_path="pyproject.toml",
            diff_hunk_ref="hunk:abcd1234",
            before_value=None,
            after_value="requests==2.32.0",
            observed_operation=ObservedOperation.ADDED,
            parser="pyproject-parser",
            parser_version="1.0.0",
            immutable_hash="hash-1",
            summary="Added requests==2.32.0 to project dependencies.",
            provenance={"event": "evt-1"},
        ),
    )


class _NoContextQuery:
    def answer_why(self, repository, question, code_area_id=None, snapshot=None, limit=5):  # noqa: E501
        from living_adr.core.graph.models import WhyAnswer

        return WhyAnswer(
            repository=repository,
            question=question,
            answer="",
            adr_id=None,
            citations=(),
            found=False,
        )

    def traverse_from_code_area(
        self,
        repository,
        code_area_id,
        relationship_types=None,
        max_depth=2,
        snapshot=None,
    ):
        return []


def _empty_context():
    from living_adr.workflow.drafting.context import build_context_request

    return package_architecture_context(
        _NoContextQuery(), build_context_request(_change())
    )


def _assemble(**kwargs) -> PromptPackage:
    return assemble_prompt(
        change=_change(),
        evidence=_evidence(),
        context=kwargs.get("context", _empty_context()),
        estimator=HeuristicTokenEstimator(),
        config=kwargs.get("config", BudgetConfig()),
    )


def test_prompt_includes_feature_004_fields() -> None:
    prompt = _assemble().user_prompt
    assert "requests" in prompt
    assert "added" in prompt
    assert "python" in prompt
    assert "direct_manifest_add" in prompt
    assert "pyproject.toml" in prompt


def test_prompt_includes_evidence_summaries() -> None:
    prompt = _assemble().user_prompt
    assert "Added requests==2.32.0 to project dependencies." in prompt


def test_prompt_includes_adr_template_sections() -> None:
    prompt = _assemble().user_prompt.lower()
    for section in ("context", "decision", "alternatives", "consequences"):
        assert section in prompt


def test_prompt_has_provisional_label() -> None:
    prompt = _assemble().user_prompt.lower()
    assert "provisional" in prompt


def test_untrusted_text_is_delimited() -> None:
    prompt = _assemble().user_prompt
    assert UNTRUSTED_DELIMITER_START in prompt
    assert UNTRUSTED_DELIMITER_END in prompt


def test_prompt_excludes_raw_diff_text() -> None:
    package = _assemble()
    # Only the diff *reference* may appear, never raw hunk text.
    assert "diff --git" not in package.user_prompt
    assert "@@" not in package.user_prompt


def test_empty_context_marks_provisional_rationale() -> None:
    package = _assemble()
    assert "no approved" in package.user_prompt.lower()


def test_prompt_carries_citations_when_context_present() -> None:
    from living_adr.core.graph.models import ADRPath, ADRRef, WhyAnswer
    from living_adr.workflow.drafting.context import (
        build_context_request,
        package_architecture_context,
    )

    class _Query:
        def answer_why(self, repository, question, code_area_id=None, snapshot=None, limit=5):  # noqa: E501
            return WhyAnswer(
                repository=repository,
                question=question,
                answer="Standardized on requests.",
                adr_id="adr-3",
                citations=("adr-3",),
                found=True,
            )

        def traverse_from_code_area(
            self,
            repository,
            code_area_id,
            relationship_types=None,
            max_depth=2,
            snapshot=None,
        ):
            ref = ADRRef(
                repository=repository,
                adr_id="adr-3",
                title="HTTP",
                status="approved",
            )
            return [
                ADRPath(
                    repository=repository,
                    code_area_id=code_area_id,
                    adrs=(ref,),
                )
            ]

    context = package_architecture_context(_Query(), build_context_request(_change()))
    package = _assemble(context=context)
    assert any(c.ref == "adr-3" for c in package.citations)
    assert "adr-3" in package.user_prompt


def test_blocked_budget_marks_package_blocked() -> None:
    package = _assemble(config=BudgetConfig(max_prompt_tokens=1))
    assert package.blocked is True
    assert package.budget_result.status is BudgetStatus.BLOCKED
