"""Approval-bound ADR publish-back orchestration (feature 011).

The :class:`ADRPublicationService` is the single publish-back entry point. It:

1. resolves the repository-scoped target from configuration (no hardcoded paths);
2. short-circuits same-``decision_id`` retries to the prior durable result
   (idempotency, FR-9) *before* re-validating — so replays after TTL expiry still
   return the prior commit instead of failing;
3. authorises every attempt through feature 010's just-in-time validation over a
   *consumed* approved decision (``validate_for_mutation`` + consumption proof) —
   the same boundary ``DurableApprovalBoundMutationService`` enforces; no SCM
   commit happens when authorisation fails (fail-closed, NFR-1);
4. reserves a durable intent record, commits the ADR Markdown through the
   injected provider-neutral :class:`PublicationCommitter` (feature 003 GitHub
   provider in production), finalises the result, and records a metadata-only
   ``PUBLICATION_LINKED`` audit row joined by ``decision_id`` (FR-2).

Numbering, slugging, and the concrete GitHub commit live behind the
:class:`PublicationCommitter` seam (slices S011-03/04), keeping this orchestration
provider-neutral and independently testable.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from living_adr.approval.models import (
    DEFAULT_DECISION_TTL,
    ApprovedReviewDecision,
    AuditEvent,
    AuditEventType,
    ConsumptionRecord,
)
from living_adr.approval.repository import ApprovalAuditRepository
from living_adr.approval.validation import validate_for_mutation
from living_adr.core.config import RepositoryConfig
from living_adr.core.graph.approval_bound_mutation import upsert_fingerprint
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.repository import RepositoryIdentity
from living_adr.publication.models import (
    DEFAULT_ADR_PATH_TEMPLATE,
    ADRPublicationRequest,
    ADRPublicationResult,
    ADRPublicationTarget,
    PublicationNotAuthorizedError,
    PublicationRecord,
    PublicationStatus,
    PublicationTargetMismatchError,
    adr_directory,
    publication_fingerprint,
)
from living_adr.publication.repository import PublicationRecordRepository

Clock = Callable[[], datetime]
IdProvider = Callable[[], str]

_NUMBER_TOKEN = re.compile(r"N+")


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _default_id() -> str:
    return str(uuid.uuid4())


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


# --- authorisation / commit seams -----------------------------------------


@dataclass(frozen=True)
class AuthorizedPublication:
    """Proof that feature 010 authorised and consumed the publishing decision."""

    decision: ApprovedReviewDecision
    consumption: ConsumptionRecord


@dataclass(frozen=True)
class CommitOutcome:
    """Result of committing the ADR Markdown through the SCM provider seam."""

    target_path: str
    commit_sha: str
    created: bool = True


@runtime_checkable
class PublicationCommitter(Protocol):
    """Provider-neutral seam that allocates the ADR path and commits it (S04).

    Implementations list the configured ADR directory through the SCM port,
    allocate the next number, render the path, detect a same-decision marker, and
    commit the approved Markdown — returning the committed path and commit SHA.
    """

    def commit(
        self,
        request: ADRPublicationRequest,
        target: ADRPublicationTarget,
        authorization: AuthorizedPublication,
    ) -> CommitOutcome: ...


class ADRPublicationService:
    """Approval-bound, idempotent ADR publish-back orchestration."""

    def __init__(
        self,
        *,
        audit: ApprovalAuditRepository,
        records: PublicationRecordRepository,
        committer: PublicationCommitter,
        observability: Observability | None = None,
        clock: Clock = _default_clock,
        ttl: timedelta = DEFAULT_DECISION_TTL,
        id_provider: IdProvider = _default_id,
    ) -> None:
        self._audit = audit
        self._records = records
        self._committer = committer
        self._obs = observability or NoOpObservability()
        self._clock = clock
        self._ttl = ttl
        self._ids = id_provider

    # ------------------------------------------------------------------ publish
    def publish(self, request: ADRPublicationRequest) -> ADRPublicationResult:
        repository = request.repository
        adr = request.adr
        decision = request.decision
        decision_key = decision.decision_id if decision is not None else "no-decision"
        fingerprint = publication_fingerprint(
            repository, adr, request.target, request.policy, decision_key
        )

        # 1. Idempotency short-circuit BEFORE re-validation (US-4): a prior
        #    successful publication for this decision returns unchanged; a prior
        #    record with a different fingerprint is a target mismatch.
        prior = (
            self._records.get(decision.decision_id) if decision is not None else None
        )
        if prior is not None:
            if prior.fingerprint != fingerprint:
                raise PublicationTargetMismatchError(
                    "this decision already published a different target"
                )
            if prior.status.is_terminal_success:
                self._obs.record_event(
                    "publication.idempotent_replay",
                    {
                        "repository": repository.key,
                        "decision_id": prior.decision_id,
                        "status": prior.status.value,
                    },
                )
                return ADRPublicationResult.from_record(
                    prior.model_copy(
                        update={"status": PublicationStatus.ALREADY_PUBLISHED}
                    ),
                    idempotent=True,
                )

        # 2. Fail-closed authorisation through the feature 010 boundary. No SCM
        #    write happens if this raises.
        authorization = self._authorize(request)

        # 3. Policy skip: livingadr_only records a decision-linked skip and never
        #    touches GitHub (US-1).
        if not request.policy.publishes_to_github:
            record = PublicationRecord(
                decision_id=decision.decision_id,
                repository_key=repository.key,
                adr_record_id=adr.adr_id,
                content_hash=adr.content_hash,
                fingerprint=fingerprint,
                target_branch=request.target.branch,
                status=PublicationStatus.SKIPPED_BY_POLICY,
                detail="publication skipped by repository policy livingadr_only",
            )
            self._records.reserve(record)
            self._link_audit(repository, authorization.decision, record)
            self._obs.record_event(
                "publication.skipped_by_policy",
                {"repository": repository.key, "decision_id": decision.decision_id},
            )
            return ADRPublicationResult.from_record(record)

        # 4. Reserve intent before the remote write (recoverable two-step).
        intent = PublicationRecord(
            decision_id=decision.decision_id,
            repository_key=repository.key,
            adr_record_id=adr.adr_id,
            content_hash=adr.content_hash,
            fingerprint=fingerprint,
            target_branch=request.target.branch,
            status=PublicationStatus.PENDING,
        )
        self._records.reserve(intent)

        # 5. Commit through the SCM provider seam.
        outcome = self._committer.commit(request, request.target, authorization)

        # 6. Finalise the durable record and link the audit by decision_id.
        committed = intent.model_copy(
            update={
                "status": PublicationStatus.COMMITTED,
                "target_path": outcome.target_path,
                "commit_sha": outcome.commit_sha,
                "detail": "published" if outcome.created else "already present",
            }
        )
        self._records.finalize(committed)
        self._link_audit(repository, authorization.decision, committed)
        self._obs.record_event(
            "publication.committed",
            {
                "repository": repository.key,
                "decision_id": decision.decision_id,
                "target_path": outcome.target_path,
                "commit_sha": outcome.commit_sha,
            },
        )
        return ADRPublicationResult.from_record(committed)

    # ----------------------------------------------------------------- helpers
    def _authorize(self, request: ADRPublicationRequest) -> AuthorizedPublication:
        decision = request.decision
        if decision is None or not decision.approved:
            raise PublicationNotAuthorizedError(
                "an approved decision is required to publish an ADR"
            )
        repository = request.repository
        expected_fp = upsert_fingerprint(repository, request.adr)
        minted = self._audit.get_minted_decision(decision.decision_id)
        # Reuse feature 010's validation byte-for-byte; it records a
        # VALIDATION_FAILED audit row and raises on any TTL/scope/content/target
        # failure (fail-closed). This is the approval boundary publish-back goes
        # through — the same checks DurableApprovalBoundMutationService applies.
        validated = validate_for_mutation(
            decision,
            repository=repository,
            expected_fingerprint=expected_fp,
            audit=self._audit,
            current_content=None,
            clock=self._clock,
            ttl=self._ttl,
            minted_record=minted,
            id_provider=self._ids,
        )

        # Proof the decision was actually consumed via the approval-bound
        # mutation boundary (decision -> graph node). Publish-back is downstream
        # of that authoritative consumption; without it there is no authority.
        consumption = self._audit.get_consumption(decision.decision_id)
        if consumption is None:
            raise PublicationNotAuthorizedError(
                "decision was not consumed through the approval-bound mutation "
                "boundary; publish-back cannot precede authoritative consumption"
            )
        return AuthorizedPublication(decision=validated, consumption=consumption)

    def _link_audit(
        self,
        repository: RepositoryIdentity,
        decision: ApprovedReviewDecision,
        record: PublicationRecord,
    ) -> None:
        # Metadata-only PUBLICATION_LINKED row (FR-2; NFR-4): identifiers, keys,
        # status, path, and commit SHA only — never the raw ADR body.
        detail = f"status={record.status.value}"
        if record.target_path:
            detail += f";path={record.target_path}"
        if record.commit_sha:
            detail += f";commit={record.commit_sha}"
        event = AuditEvent(
            audit_id=self._ids(),
            event_type=AuditEventType.PUBLICATION_LINKED,
            repository_key=repository.key,
            recorded_at=self._clock(),
            decision_id=decision.decision_id,
            reviewer_id=decision.reviewer_id,
            target_fingerprint=record.fingerprint,
            detail=detail,
        )
        self._audit.record_audit_event(event)


__all__ = [
    "resolve_publication_target",
    "AuthorizedPublication",
    "CommitOutcome",
    "PublicationCommitter",
    "ADRPublicationService",
]
