# Quality Checklist: tracked-repository-configuration

## CRISPY Phase Gates

### 🔬 C — Research

- [ ] `research.md` states that `living-adr` is greenfield and no production code exists yet under `C:\repos`.
- [ ] `research.md` references `..\..\architecture.md#data-model`, `#cross-cutting`, `#service-boundaries`, `#repositories`, and `#deployment`.
- [ ] Relevant domain failure modes FM-14, FM-15, FM-16, FM-17, FM-21, FM-23, and FM-24 are carried forward.
- [ ] Research distinguishes pure local validation from later live GitHub onboarding checks.
- [ ] Research documents testing patterns for config validation, startup diagnostics, restart semantics, and no-op observability.

### 🎯 R — Sound Intent

- [ ] `intent.md` maps current architecture to desired state in a gap-analysis table.
- [ ] At least 3 architecture options are evaluated.
- [ ] Selected approach is Pydantic core config models with shared loader.
- [ ] Anti-patterns include hardcoded PoC repo, single-repo branching, implicit external LLM allow, LangSmith imports in core, and hot reload.
- [ ] Affected repository `living-adr` is listed with high confidence.
- [ ] Module Surface Analysis identifies isolated-test candidates for config, repository identity, observability, and startup helpers.
- [ ] `intent.md` explicitly describes the no-op `Observability` port contract.

### 🍕 I — Vertical Slices

- [ ] `outline.md` contains exactly 5 slices.
- [ ] Each slice delivers independently testable behavior.
- [ ] Slice dependencies are mapped and ordered correctly.
- [ ] `outline.md` includes both human-readable and machine-readable dependency graphs.
- [ ] Every slice includes `automation: HITL | AFK` and `automation_reason`.
- [ ] Automation classifications agree between `outline.md` and `implementation-manifest.yaml`.
- [ ] No slice requires more than one focused implementation session.

### 📋 S — Tactical Plan

- [ ] Every implementation step references specific file paths relative to `living-adr`.
- [ ] New files and modified files are clearly distinguished.
- [ ] `plan.md` includes a fenced YAML `task_graph` with one entry per implementation task.
- [ ] Task IDs in `plan.md` align with `tasks.md`.
- [ ] Complexity estimates are provided per phase.
- [ ] Rollback strategy is documented per phase.
- [ ] No production-code change is included in this planning feature folder.

### 🧹 P — Fresh Context

- [ ] `outline.md` identifies context reset points after Slice 1 and after Slice 3.
- [ ] Each slice lists key files needed in context.
- [ ] Shared state to carry across slices is explicitly listed.
- [ ] Slices do not require hidden knowledge outside the inherited project artifacts and generated feature docs.

### 📝 Y — Task Yield

- [ ] `tasks.md` organizes tasks by user story.
- [ ] Every functional task has a RED test task before GREEN implementation where practical.
- [ ] Every task is intended to be completable in less than 2 hours.
- [ ] Dependencies between tasks are explicit.
- [ ] Parallel opportunities list only tasks with separate files or no write conflicts.
- [ ] Verification tasks include pytest, Ruff, and no-LangSmith-core confirmation.

### 🧪 No Horizontal Slicing (L3)

- [ ] Tasks are ordered by behavior: identity, config collection, loader/startup, policy, lifecycle, observability.
- [ ] Tests and implementation for each behavior stay adjacent.
- [ ] No slice batches all tests first across unrelated behaviors.
- [ ] Reviewers should flag premature GitHub, Claude, LangSmith, graph, or MCP implementation as scope creep.

## Feature-Specific Quality Gates

### Configuration validation

- [ ] Valid one-repository config validates through the same list path as multiple repositories.
- [ ] `repositories` list rejects empty input.
- [ ] Duplicate canonical `RepositoryIdentity` values fail validation.
- [ ] Missing `host`, `owner`, `repo`, or `repo_id` fails validation with field-level detail.
- [ ] `RepositoryConfig` carries no secrets such as API keys, private keys, webhook secrets, or UI tokens.
- [ ] Startup error messages are clear enough to identify the config path and invalid field.

### Publication policy and LLM egress

- [ ] `livingadr_only` parses and does not require write-back permissions.
- [ ] `publish_to_github` parses and requires valid target branch/path template.
- [ ] `publish_to_github_and_livingadr` parses and requires valid target branch/path template.
- [ ] Unknown publication-policy values fail startup validation.
- [ ] `external_llm_allowed: true` and `external_llm_allowed: false` are both parsed and test-covered.
- [ ] Omitted external LLM policy does not silently allow egress.

### Startup and lifecycle

- [ ] Default config path is used when `LIVING_ADR_CONFIG` is unset.
- [ ] `LIVING_ADR_CONFIG` override path is honored.
- [ ] Workflow service startup fails before readiness on invalid config.
- [ ] MCP context server startup fails before serving tools/resources on invalid config.
- [ ] Existing in-memory config does not change when the file changes after startup.
- [ ] No file watcher, background reload task, or per-request config parse is introduced.
- [ ] Documentation/sample config states both deployables require restart after config changes.

### Observability no-op port

- [ ] `Observability` port is defined in core without LangSmith import.
- [ ] `NoOpObservability` implements event, counter, and span/context-manager behavior.
- [ ] No-op implementation performs no network I/O and does not require API keys.
- [ ] Span context manager exits cleanly on success and exception paths.
- [ ] Contract documentation states default-deny raw export categories: raw diffs, full prompts, provisional drafts, reviewer comments, secrets, and retrieved context.
- [ ] Feature 013 remains responsible for LangSmith implementation behind this port.

## Pre-Implementation Checks

- [ ] All 8 requested artifacts exist in `features\002-tracked-repository-configuration`.
- [ ] No files outside the feature folder were modified during planning.
- [ ] `implementation-manifest.yaml` has `ready: true` only if all artifacts are internally consistent.
- [ ] `implementation-manifest.yaml` includes feature id `002`, slice count `5`, dependencies `[]`, and success metric links.
- [ ] No unresolved open question blocks implementation; non-blocking implementation choices are documented.
- [ ] Implementation base/current branch identified in the `living-adr` repo before coding begins.
- [ ] Development environment is set up according to `..\..\architecture.md#tech-stack` before coding begins.

## Implementation Checks (per task)

- [ ] Task matches the plan and does not add unrelated features.
- [ ] Tests are written before or alongside implementation.
- [ ] No unrelated changes are included.
- [ ] Code follows architecture package layout under `src\living_adr`.
- [ ] Checkpoint criteria from `outline.md` are met before moving to the next slice.
- [ ] Existing tests, Ruff checks, and startup tests pass after changes.

## Source-Learning and Contract Traceability

- [ ] Planning artifacts preserve source-of-truth hierarchy from `..\..\architecture.md#cross-cutting`: code/PR data is evidence, ADRs are authoritative rationale, graph nodes are projections.
- [ ] Public-agent/MCP boundary remains read-only and repository-scoped.
- [ ] Transcript/caption limitation is not applicable to this feature; no artifact introduces media/transcript processing.
- [ ] Interface contracts are planned as code-level ports under `src\living_adr\core`, not a legacy `contracts.md` file.
- [ ] `CONTEXT.md` is not required for this feature because the user requested exactly 8 planning artifacts; canonical terms are captured inside `spec.md`, `research.md`, and `intent.md`.
