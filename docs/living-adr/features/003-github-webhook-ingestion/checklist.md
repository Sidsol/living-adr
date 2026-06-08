# Quality Checklist: github-webhook-ingestion

## CRISPY Phase Gates

### 🔬 C — Research

- [ ] `research.md` states that `living-adr` is greenfield and no production webhook ingestion code exists yet under the planning target.
- [ ] `research.md` references `..\..\architecture.md#service-boundaries`, `#data-model`, `#cross-cutting`, and `#anti-patterns`.
- [ ] Research carries forward FM-17 webhook replay, FM-18 rate-limit starvation, FM-24 cross-SCM abstraction leaks, FM-14 untrusted input, and FM-21 trace leakage.
- [ ] Research distinguishes Feature 002 config/observability contracts from Feature 003 ingestion responsibilities.
- [ ] Research documents integration points for GitHub webhooks, GitHub REST API, SQLite state, config, observability, and future Azure DevOps service hooks.

### 🎯 R — Sound Intent

- [ ] `intent.md` maps current architecture to desired state in a gap-analysis table.
- [ ] `intent.md` explicitly references `..\..\architecture.md#service-boundaries`, `#data-model`, `#cross-cutting`, and `#anti-patterns`.
- [ ] At least 3 architecture options are evaluated.
- [ ] Selected approach is provider-neutral core event and `SCMProvider` port with `GitHubProvider` adapter.
- [ ] Module Surface Analysis identifies isolated-test candidates for `SCMEvent`, HMAC verification, idempotency, GitHub provider, evidence builder, replay, and ingestion store.
- [ ] Anti-patterns include parsing JSON before HMAC verification, PR-number-only idempotency, raw GitHub payload leakage, broad history fetch, evidence-as-rationale, raw observability export, and full LangGraph checkpointing in this feature.
- [ ] Affected repository `living-adr` is listed with high confidence.

### 🍕 I — Vertical Slices

- [ ] `outline.md` contains exactly 6 slices.
- [ ] Each slice delivers independently testable behavior.
- [ ] Slice dependencies are mapped and ordered correctly.
- [ ] `outline.md` includes both human-readable and machine-readable dependency graphs.
- [ ] Every slice includes `automation: HITL | AFK` and `automation_reason`.
- [ ] Automation classifications agree between `outline.md` and `implementation-manifest.yaml`.
- [ ] No slice requires more than one focused implementation session.

### 📋 S — Tactical Plan

- [ ] Every implementation step references specific file paths relative to the future `living-adr` repo.
- [ ] New files and modified files are clearly distinguished.
- [ ] `plan.md` includes a fenced YAML `task_graph` with one entry per implementation task.
- [ ] Task IDs in `plan.md` align with `tasks.md`.
- [ ] Complexity estimates are provided per phase.
- [ ] Rollback strategy is documented per phase.
- [ ] No production-code change is included in this planning feature folder.

### 🧹 P — Fresh Context

- [ ] `outline.md` identifies context reset points after Slice 2 and after Slice 4.
- [ ] Each slice lists key files needed in context.
- [ ] Shared state to carry across slices is explicitly listed.
- [ ] Slices do not require hidden knowledge outside inherited project artifacts and generated feature docs.

### 📝 Y — Task Yield

- [ ] `tasks.md` organizes tasks by user story.
- [ ] Every functional behavior has a RED test task before GREEN implementation where practical.
- [ ] Every task is intended to be completable in less than 2 hours.
- [ ] Dependencies between tasks are explicit.
- [ ] Parallel opportunities list only genuinely safe tasks.
- [ ] Verification tasks include pytest, Ruff, raw-payload seam, and observability hygiene checks.

### 🧪 No Horizontal Slicing (L3)

- [ ] Tasks are ordered by behavior: HMAC, filtering/idempotency, normalization, provider/evidence, replay/dead-letter, observability/E2E.
- [ ] Tests and implementation for each behavior stay adjacent.
- [ ] No slice batches all tests first across unrelated behaviors.
- [ ] Reviewers should flag premature classifiers, Claude drafting, HITL, graph mutation, MCP query, Azure DevOps implementation, or full LangGraph checkpointing as scope creep.

## Feature-Specific Quality Gates

### HMAC verified

- [ ] `X-Hub-Signature-256` is verified against raw request bytes before JSON parsing.
- [ ] Invalid/missing/malformed signatures create no `SCMEvent`, evidence, provider call, or classifier handoff.
- [ ] Constant-time comparison is used for signature checks.
- [ ] Tests cover body tampering and signature algorithm mismatch.
- [ ] Webhook secret is consumed from env/vault configuration, not `RepositoryConfig` and not source code.

### Idempotency on delivery-id

- [ ] GitHub `X-GitHub-Delivery` is required and persisted as provider delivery id.
- [ ] Duplicate delivery ids return prior outcome without duplicate `SCMEvent` or evidence.
- [ ] Normalized PR key is repository-scoped and does not rely on PR number alone.
- [ ] Delivery state includes accepted, skipped, failed, replayed, and dead-letter outcomes.
- [ ] Conflicting duplicate metadata is handled deterministically and audited/observed safely.

### SCMEvent normalized

- [ ] `SCMEvent` includes `RepositoryIdentity`, provider, provider event type, delivery id, normalized PR key, timestamps, PR number, refs, merge SHA, and fetch handles.
- [ ] Workflow-facing code does not traverse raw GitHub payload dictionaries.
- [ ] Provider-specific fields remain in adapter metadata or fetch handles.
- [ ] `SCMProvider` methods accept `RepositoryIdentity` scope.
- [ ] Candidate evidence links back to `SCMEvent`, delivery id, normalized PR key, and fetch provenance.

### Replay/dead-letter handled

- [ ] Retryable provider errors are distinguishable from poison/malformed events.
- [ ] Dead-letter records include error category, retry count, state, repository key if known, and normalized PR key if known.
- [ ] Replay uses stored delivery/event data and preserves idempotency.
- [ ] Replay does not require GitHub to resend the webhook.
- [ ] Dead-letter metadata excludes raw secrets, raw webhook bodies, and raw diffs.

### Azure DevOps seam preserved

- [ ] No core model requires GitHub-only field names as mandatory workflow-facing fields.
- [ ] GitHub event taxonomy and permissions stay inside `scm\github_*` modules.
- [ ] `SCMProvider` is provider-neutral enough for future Azure DevOps service hooks and PR APIs.
- [ ] Tests or contract docs describe how non-GitHub providers map into `SCMEvent` without changing workflow nodes.
- [ ] No implementation introduces `if provider == github` branches in classifier-facing workflow code.

### Minimal GitHub evidence and rate-limit discipline

- [ ] GitHub provider fetches only PR metadata, changed files, and diff text/handle needed for V1.
- [ ] Broad repository history mining/backfill is not implemented.
- [ ] Fetched evidence is cached or persisted enough to avoid duplicate API calls on retry/replay.
- [ ] Rate-limit, permission, missing-resource, and transient failures are test-covered.

### Observability hygiene

- [ ] Feature uses Feature 002 `Observability` port; no direct LangSmith dependency is introduced.
- [ ] Observability metadata includes only safe fields such as repository key, event type, delivery id, outcome, latency, retry count, and error category.
- [ ] Raw webhook bodies, raw diffs, secrets, prompts, drafts, reviewer comments, and retrieved context are not exported.
- [ ] Counters/spans cover verification, idempotency, filtering, normalization, provider fetch, evidence creation, replay, and dead-letter outcomes.

## Pre-Implementation Checks

- [ ] All 8 requested artifacts exist in `features\003-github-webhook-ingestion`.
- [ ] No files outside the feature folder were modified during planning.
- [ ] `implementation-manifest.yaml` has `ready: true` only if all artifacts are internally consistent.
- [ ] `implementation-manifest.yaml` includes feature id `003`, slice count `6`, dependency `002`, and downstream feature links.
- [ ] No unresolved open question blocks implementation; local webhook delivery path and exact permissions are implementation/onboarding details.
- [ ] Implementation base/current branch is identified in the future `living-adr` repo before coding begins.
- [ ] Feature 002 config/observability contracts are available before coding begins.

## Implementation Checks (per task)

- [ ] Task matches the plan and does not add unrelated features.
- [ ] Tests are written before or alongside implementation.
- [ ] No unrelated changes are included.
- [ ] Code follows architecture package layout under `src\living_adr`.
- [ ] Checkpoint criteria from `outline.md` are met before moving to the next slice.
- [ ] Existing tests and Ruff checks pass after changes.

## Source-Learning and Contract Traceability

- [ ] Planning artifacts preserve source-of-truth hierarchy from `..\..\architecture.md#cross-cutting`: code/PR data is evidence, ADRs are authoritative rationale, graph nodes are projections.
- [ ] Public-agent/MCP boundary remains read-only and is not expanded by this feature.
- [ ] Transcript/caption limitation is not applicable to this feature; no artifact introduces media/transcript processing.
- [ ] Interface contracts are planned as code-level ports under `src\living_adr\core`, not a legacy `contracts.md` file.
- [ ] `CONTEXT.md` is not required for this feature because the user requested exactly 8 planning artifacts; canonical terms are captured inside `spec.md`, `research.md`, and `intent.md`.
