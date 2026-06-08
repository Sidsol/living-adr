"""Pull-request publish-back of an approved ADR (feature 011, PR mode).

After the workflow settles ``COMPLETED`` (a human approved the draft and the
approval-bound graph write succeeded with a valid one-shot capability), this
publisher commits the approved ADR Markdown to a fresh branch and opens a pull
request into the configured target branch. It reuses the tested ADR
numbering/slugging/path rendering and the decision marker for idempotent
recovery (a stable per-decision branch + the marker mean re-runs do not create
duplicates).

Approval gating: publishing only runs for a COMPLETED, authorising outcome, so a
PR is never opened without an approval that already drove the approval-bound
graph mutation. Telemetry is metadata-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.scm import CommitConflictError, SCMProviderError
from living_adr.publication.models import DEFAULT_ADR_PATH_TEMPLATE, adr_directory
from living_adr.publication.numbering import (
    embed_decision_marker,
    next_adr_number,
    render_adr_path,
)
from living_adr.publication.slugging import slugify
from living_adr.workflow.state import ReviewResumeCommand, WorkflowStatus

if TYPE_CHECKING:
    from typing import Any

    from living_adr.core.config import LivingADRConfig
    from living_adr.hitl.gateway import ResumeOutcome, ReviewWorkflowGateway
    from living_adr.scm.github_provider import PullRequestHandle

DEFAULT_BRANCH_PREFIX = "livingadr/adr"


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _normalize_template(template: str) -> str:
    """Accept either ``{number}``/``{slug}`` or ``NNNN``/``<slug>`` token styles."""

    return template.replace("{number}", "NNNN").replace("{slug}", "<slug>")


class PullRequestPublisher:
    """Opens a pull request carrying the approved ADR Markdown."""

    def __init__(
        self,
        provider: Any,
        config: LivingADRConfig,
        *,
        branch_prefix: str = DEFAULT_BRANCH_PREFIX,
        observability: Observability | None = None,
    ) -> None:
        self._provider = provider
        self._config = config
        self._prefix = branch_prefix
        self._obs: Observability = observability or NoOpObservability()

    def publish_completed(self, values: dict[str, Any]) -> PullRequestHandle | None:
        """Open a PR for a COMPLETED workflow's approved draft (or ``None``)."""

        repository = values.get("repository")
        draft = values.get("draft")
        decision = values.get("approved_decision")
        if repository is None or draft is None or decision is None:
            return None

        repo_config = self._config.get(repository.key)
        if repo_config is None or not (
            repo_config.adr_publication_policy.publishes_to_github
        ):
            return None

        base = repo_config.adr_target_branch or repo_config.default_branch
        template = _normalize_template(
            repo_config.adr_path_template or DEFAULT_ADR_PATH_TEMPLATE
        )
        directory = adr_directory(template)
        files = self._provider.list_directory(repository, base, directory)
        number = next_adr_number(f.name for f in files)
        title = _extract_title(draft.preview) or f"ADR {draft.draft_id}"
        slug = slugify(title, fallback_id=draft.draft_id)
        path = render_adr_path(template, number, slug)
        markdown = embed_decision_marker(draft.preview, decision.decision_id)

        base_sha = self._provider.get_branch_head_sha(repository, base)
        branch = f"{self._prefix}-{decision.decision_id[:12]}"
        self._provider.create_branch(repository, branch, base_sha)
        try:
            self._provider.create_file(
                repository, branch, path, markdown, f"Add ADR: {title}"
            )
        except CommitConflictError:
            # Already committed on this decision's branch (idempotent re-run).
            pass

        try:
            pull_request = self._provider.open_pull_request(
                repository,
                title=f"ADR: {title}",
                head=branch,
                base=base,
                body=(
                    "Automated LivingADR publish of an approved Architecture "
                    "Decision Record.\n\n"
                    f"- Path: `{path}`\n- Decision: `{decision.decision_id}`\n"
                ),
            )
        except SCMProviderError:
            # PR already open for this branch (or transient) — never fail review.
            self._obs.record_event(
                "publication.pr_open_skipped",
                {"repository": repository.key, "branch": branch},
            )
            return None

        self._obs.record_event(
            "publication.pr_opened",
            {
                "repository": repository.key,
                "pr_number": pull_request.number,
                "path": path,
            },
        )
        return pull_request


class PublishingReviewGateway:
    """HITL gateway that publishes a PR after a COMPLETED, approving resume.

    Delegates pending/list/resume to an inner gateway; after an authorising
    resume settles ``COMPLETED`` it reads the final state and opens the PR.
    Publishing failures are swallowed (metadata-only) so they never fail the
    reviewer's already-recorded decision.
    """

    def __init__(
        self,
        inner: ReviewWorkflowGateway,
        service: Any,
        publisher: PullRequestPublisher,
        *,
        observability: Observability | None = None,
    ) -> None:
        self._inner = inner
        self._service = service
        self._publisher = publisher
        self._obs: Observability = observability or NoOpObservability()

    def get_pending_review(self, thread_id: str):
        return self._inner.get_pending_review(thread_id)

    def list_pending(self):
        return self._inner.list_pending()

    def submit_resume(
        self, thread_id: str, command: ReviewResumeCommand
    ) -> ResumeOutcome:
        outcome = self._inner.submit_resume(thread_id, command)
        if (
            outcome.status is WorkflowStatus.COMPLETED
            and command.action.authorizes_mutation
        ):
            run = self._service.inspect(thread_id)
            if run is not None:
                try:
                    self._publisher.publish_completed(dict(run.values))
                except Exception as exc:  # noqa: BLE001 - never fail the review
                    self._obs.record_event(
                        "publication.failed",
                        {
                            "thread_id": thread_id,
                            "error_class": type(exc).__name__,
                        },
                    )
        return outcome


__all__ = ["PullRequestPublisher", "PublishingReviewGateway"]
