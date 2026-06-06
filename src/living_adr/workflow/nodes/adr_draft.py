"""Feature-015 ADR draft node — Claude drafting integration (feature 008, S-006).

This is the real :class:`~living_adr.workflow.nodes.protocols.ADRDraftNode` that
replaces feature 015's deterministic stub. It composes the drafting services —
policy gate, graph-context packaging, token budget, prompt assembly, the Claude
client seam, and the Markdown parser — into a single node that:

* consumes Feature 004 production ``StructuralChange`` + ``ChangeEvidence``
  (resolved from workflow state via an injected :class:`DraftInputResolver`);
* enforces the external-LLM policy **before** any prompt assembly or egress;
* returns a provisional :class:`~living_adr.workflow.state.DraftRef` on success;
* routes every typed non-draft outcome (FR-9) onto the feature-015 state shape;
* performs **no** authoritative mutation, approval, audit, or publish action —
  drafts are inert until downstream HITL approval (NFR-1).

The node only updates the draft/status/error fields of ``WorkflowState`` the
feature-015 seam expects; it never touches ``mutation_result`` or
``approved_decision`` (US-6).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from living_adr.approval.hashing import canonical_adr_hash
from living_adr.core.adr_draft import (
    ADRDraft,
    CitationKind,
    DraftCitation,
    DraftingOutcome,
    ModelMetadata,
    compute_draft_content_hash,
)
from living_adr.core.config import RepositoryConfig
from living_adr.core.llm import ClaudeClient, ClaudeError, ClaudeRequest
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeEvidence,
    StructuralChange,
)
from living_adr.observability.drafting_events import (
    DRAFTING_BUDGET_BLOCKED,
    DRAFTING_COMPLETED,
    DRAFTING_INVALID_OUTPUT,
    DRAFTING_POLICY_BLOCKED,
    DRAFTING_PROVIDER_ERROR,
    DRAFTING_STARTED,
    DRAFTING_SUCCEEDED,
    budget_blocked_metadata,
    completed_metadata,
    invalid_output_metadata,
    policy_blocked_metadata,
    provider_error_metadata,
    started_metadata,
    succeeded_metadata,
)
from living_adr.workflow.drafting.context import (
    ContextQuery,
    PackagedContext,
    build_context_request,
    package_architecture_context,
)
from living_adr.workflow.drafting.parser import DraftParseError, parse_adr_markdown
from living_adr.workflow.drafting.policy import evaluate_external_llm_policy
from living_adr.workflow.drafting.prompt import assemble_prompt
from living_adr.workflow.drafting.token_budget import (
    BudgetConfig,
    HeuristicTokenEstimator,
    TokenEstimator,
)
from living_adr.workflow.nodes.protocols import StateUpdate
from living_adr.workflow.state import (
    DraftRef,
    WorkflowError,
    WorkflowState,
    WorkflowStatus,
)

DEFAULT_MODEL_ID = "claude-sonnet-4-6"
DEFAULT_MAX_OUTPUT_TOKENS = 2000


class DraftInputs(BaseModel):
    """Resolved drafting inputs: the production contracts a draft is built from."""

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    change: StructuralChange
    evidence: tuple[ChangeEvidence, ...]
    repository_config: RepositoryConfig


@runtime_checkable
class DraftInputResolver(Protocol):
    """Resolves feature-015 workflow state into production drafting inputs.

    Returning ``None`` means there is no draft-eligible change in the current
    state (the node records a no-ADR outcome and makes no Claude call).
    """

    def resolve(self, state: WorkflowState) -> DraftInputs | None: ...


class DraftingResult(BaseModel):
    """The typed outcome of a single drafting attempt (metadata-safe)."""

    model_config = ConfigDict(frozen=True)

    outcome: DraftingOutcome
    draft: ADRDraft | None = None
    detail: str = ""
    error_class: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    model_id: str | None = None


class DraftingService:
    """Pure composition of the drafting pipeline over production contracts.

    Kept separate from the node so it can be unit-tested without a
    ``WorkflowState`` and reused by the node's state mapping.
    """

    def __init__(
        self,
        *,
        claude_client: ClaudeClient,
        estimator: TokenEstimator | None = None,
        budget_config: BudgetConfig | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> None:
        self._client = claude_client
        self._estimator = estimator or HeuristicTokenEstimator()
        self._budget = budget_config or BudgetConfig()
        self._model_id = model_id
        self._max_output_tokens = max_output_tokens

    def draft(
        self, inputs: DraftInputs, *, context_query: ContextQuery | None = None
    ) -> DraftingResult:
        change = inputs.change

        if change.adr_recommendation is ADRRecommendation.NO_ADR_NEEDED:
            return DraftingResult(
                outcome=DraftingOutcome.NO_ADR_NEEDED,
                detail="change is not draft-eligible",
            )

        policy = evaluate_external_llm_policy(inputs.repository_config)
        if not policy.allowed:
            return DraftingResult(
                outcome=DraftingOutcome.LLM_POLICY_DENIED,
                detail=policy.reason,
            )

        if not inputs.evidence:
            return DraftingResult(
                outcome=DraftingOutcome.MISSING_EVIDENCE,
                detail="no change evidence available to ground the draft",
            )

        context = self._package_context(change, context_query)
        package = assemble_prompt(
            change=change,
            evidence=inputs.evidence,
            context=context,
            estimator=self._estimator,
            config=self._budget,
        )
        if package.blocked:
            return DraftingResult(
                outcome=DraftingOutcome.BUDGET_EXCEEDED,
                detail=package.budget_result.note,
            )

        request = ClaudeRequest(
            model_id=self._model_id,
            system=package.system,
            prompt=package.user_prompt,
            max_tokens=self._max_output_tokens,
        )
        try:
            response = self._client.complete(request)
        except ClaudeError as exc:
            return DraftingResult(
                outcome=DraftingOutcome.PROVIDER_ERROR,
                detail="claude provider call failed",
                error_class=exc.error_class,
                model_id=self._model_id,
            )

        try:
            parsed = parse_adr_markdown(response.text)
        except DraftParseError as exc:
            return DraftingResult(
                outcome=DraftingOutcome.INVALID_OUTPUT,
                detail=str(exc),
                error_class="invalid_output",
                model_id=response.model_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

        citations = self._resolve_citations(parsed.citations, inputs, context)
        content_hash = compute_draft_content_hash(
            repository=change.repository,
            structural_change_id=change.id,
            title=parsed.title,
            context=parsed.context,
            decision=parsed.decision,
            alternatives=parsed.alternatives,
            consequences=parsed.consequences,
            citations=citations,
        )
        draft = ADRDraft(
            repository=change.repository,
            draft_id=f"draft-{change.id}",
            structural_change_id=change.id,
            title=parsed.title,
            status="proposed",
            context=parsed.context,
            decision=parsed.decision,
            alternatives=parsed.alternatives,
            consequences=parsed.consequences,
            citations=citations,
            rendered_markdown=parsed.raw_markdown,
            model_metadata=ModelMetadata(
                model_id=response.model_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                stop_reason=response.stop_reason,
            ),
            content_hash=content_hash,
            provisional=True,
        )
        return DraftingResult(
            outcome=DraftingOutcome.DRAFTED,
            draft=draft,
            model_id=response.model_id,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    def _package_context(
        self, change: StructuralChange, context_query: ContextQuery | None
    ) -> PackagedContext:
        if context_query is None:
            request = build_context_request(change)
            return PackagedContext(
                repository=change.repository,
                question=request.question,
                is_empty=True,
                empty_marker=(
                    "No approved architecture context source configured; "
                    "rationale is provisional."
                ),
            )
        return package_architecture_context(
            context_query, build_context_request(change)
        )

    @staticmethod
    def _resolve_citations(
        cited_refs: tuple[str, ...],
        inputs: DraftInputs,
        context: PackagedContext,
    ) -> tuple[DraftCitation, ...]:
        """Keep only citations that resolve to known evidence/approved ADR ids.

        Hallucinated citation ids (not present in the supplied evidence or
        approved context) are dropped rather than trusted (anti-pattern: PR/model
        overtrust).
        """

        evidence_ids = {item.id for item in inputs.evidence}
        adr_ids = {citation.ref for citation in context.citations}
        resolved: list[DraftCitation] = []
        for ref in cited_refs:
            if ref in evidence_ids:
                resolved.append(DraftCitation(kind=CitationKind.EVIDENCE, ref=ref))
            elif ref in adr_ids:
                resolved.append(DraftCitation(kind=CitationKind.ADR, ref=ref))
        return tuple(resolved)


_FAILED_OUTCOMES = {
    DraftingOutcome.LLM_POLICY_DENIED,
    DraftingOutcome.BUDGET_EXCEEDED,
    DraftingOutcome.MISSING_EVIDENCE,
    DraftingOutcome.PROVIDER_ERROR,
    DraftingOutcome.INVALID_OUTPUT,
}


class ClaudeADRDraftNode:
    """Feature-015 ``ADRDraftNode`` backed by Claude (the real draft node)."""

    def __init__(
        self,
        *,
        resolver: DraftInputResolver,
        claude_client: ClaudeClient,
        context_query: ContextQuery | None = None,
        estimator: TokenEstimator | None = None,
        budget_config: BudgetConfig | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        observability: Observability | None = None,
    ) -> None:
        self._resolver = resolver
        self._context_query = context_query
        self._observability = observability or NoOpObservability()
        self._model_id = model_id
        self._service = DraftingService(
            claude_client=claude_client,
            estimator=estimator,
            budget_config=budget_config,
            model_id=model_id,
        )

    def __call__(self, state: WorkflowState) -> StateUpdate:
        inputs = self._resolver.resolve(state)
        if inputs is None:
            return {"status": WorkflowStatus.NO_ADR_NEEDED}

        repo_key = inputs.repository.key
        change_id = inputs.change.id
        event_key = state.normalized_event_key
        self._observability.record_event(
            DRAFTING_STARTED,
            started_metadata(
                repository_key=repo_key,
                structural_change_id=change_id,
                model_id=self._model_id,
                normalized_event_key=event_key,
            ),
        )

        result = self._service.draft(inputs, context_query=self._context_query)
        self._emit_outcome(repo_key, change_id, event_key, result)

        self._observability.record_event(
            DRAFTING_COMPLETED,
            completed_metadata(
                repository_key=repo_key,
                structural_change_id=change_id,
                result_type=result.outcome.value,
                normalized_event_key=event_key,
            ),
        )
        return self._to_state_update(inputs, result)

    def _emit_outcome(
        self,
        repo_key: str,
        change_id: str,
        event_key: str | None,
        result: DraftingResult,
    ) -> None:
        """Emit the metadata-only event matching the typed outcome (US-7)."""

        outcome = result.outcome
        if outcome is DraftingOutcome.LLM_POLICY_DENIED:
            self._observability.record_event(
                DRAFTING_POLICY_BLOCKED,
                policy_blocked_metadata(
                    repository_key=repo_key,
                    structural_change_id=change_id,
                    reason=result.detail or "external_llm_denied",
                    normalized_event_key=event_key,
                ),
            )
        elif outcome is DraftingOutcome.BUDGET_EXCEEDED:
            self._observability.record_event(
                DRAFTING_BUDGET_BLOCKED,
                budget_blocked_metadata(
                    repository_key=repo_key,
                    structural_change_id=change_id,
                    normalized_event_key=event_key,
                ),
            )
        elif outcome is DraftingOutcome.PROVIDER_ERROR:
            self._observability.record_event(
                DRAFTING_PROVIDER_ERROR,
                provider_error_metadata(
                    repository_key=repo_key,
                    structural_change_id=change_id,
                    model_id=result.model_id or self._model_id,
                    error_class=result.error_class or "provider_error",
                    normalized_event_key=event_key,
                ),
            )
        elif outcome is DraftingOutcome.INVALID_OUTPUT:
            self._observability.record_event(
                DRAFTING_INVALID_OUTPUT,
                invalid_output_metadata(
                    repository_key=repo_key,
                    structural_change_id=change_id,
                    model_id=result.model_id or self._model_id,
                    normalized_event_key=event_key,
                ),
            )
        elif outcome is DraftingOutcome.DRAFTED and result.draft is not None:
            self._observability.record_event(
                DRAFTING_SUCCEEDED,
                succeeded_metadata(
                    repository_key=repo_key,
                    structural_change_id=change_id,
                    model_id=result.model_id or self._model_id,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    content_hash=result.draft.content_hash,
                    citation_count=len(result.draft.citations),
                    normalized_event_key=event_key,
                ),
            )

    def _to_state_update(
        self, inputs: DraftInputs, result: DraftingResult
    ) -> StateUpdate:
        if result.outcome is DraftingOutcome.DRAFTED and result.draft is not None:
            draft = result.draft
            return {
                "draft": DraftRef(
                    draft_id=draft.draft_id,
                    # Bind the review/approval to the canonical hash of the exact
                    # rendered Markdown body the reviewer sees and that the
                    # approval-bound mutation re-validates (feature 006/010), so
                    # the content-drift check holds for real drafts.
                    content_hash=canonical_adr_hash(draft.rendered_markdown),
                    preview=draft.rendered_markdown,
                    citation_ids=tuple(c.ref for c in draft.citations),
                    structural_change_id=draft.structural_change_id,
                    provisional=True,
                ),
                "status": WorkflowStatus.DRAFTING,
            }

        if result.outcome is DraftingOutcome.NO_ADR_NEEDED:
            return {"status": WorkflowStatus.NO_ADR_NEEDED}

        return {
            "error": WorkflowError(
                node="adr_draft",
                category=result.outcome.value,
                detail=result.detail,
            ),
            "status": WorkflowStatus.FAILED,
        }


__all__ = [
    "DEFAULT_MODEL_ID",
    "DraftInputs",
    "DraftInputResolver",
    "DraftingResult",
    "DraftingService",
    "ClaudeADRDraftNode",
]
