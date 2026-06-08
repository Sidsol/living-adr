# Feature Specification: claude-adr-drafting-capability

## Overview
Feature 008 delivers LivingADR's first end-to-end ADR draft generation capability. It reads Feature 004 dependency `StructuralChange` records and linked immutable `ChangeEvidence`, fetches approved architecture context through Feature 007's `ArchitectureContextQuery`, and runs as the real draft node within Feature 015's LangGraph workflow seam. It adds a fakeable `ClaudeClient`, repository LLM allow/deny enforcement, token-budgeted prompt assembly, Claude output validation, and a provisional draft `ADRRecord`/`ADRDraft` result.

This feature performs **no authoritative mutations**. Approval, persistence, audit durability, graph mutation, and GitHub publication remain downstream features.

## User Stories

### [US-1] Grounded ADR draft generation — Priority: P1
**As a** tech lead, **I want** a Markdown ADR draft generated from a dependency change, **so that** I can review architectural rationale quickly.

#### Acceptance Scenarios
- **Given** a Feature 004 `StructuralChange` with `adr_recommendation="draft"` and linked `ChangeEvidence`, **When** the draft node runs, **Then** it returns a provisional ADR draft with title, status, context, decision, alternatives, consequences, evidence citations, model metadata, and content hash.
- **Given** the change is `no_adr_needed`, **When** the node runs, **Then** it records a no-draft outcome and does not call Claude.

### [US-2] Architecture context retrieval — Priority: P1
**As a** drafting workflow, **I want** approved graph context via `ArchitectureContextQuery`, **so that** drafts cite existing architecture decisions.

#### Acceptance Scenarios
- **Given** relevant approved ADR/context exists, **When** prompt assembly runs, **Then** it uses repository-scoped query-port calls and includes bounded citations.
- **Given** no relevant context exists, **When** drafting runs, **Then** the prompt states approved context is absent and labels rationale as provisional.

### [US-3] Per-repository LLM policy — Priority: P1
**As a** repository owner, **I want** external LLM policy enforced before egress, **so that** disallowed repository data is never sent to Claude.

#### Acceptance Scenarios
- **Given** `external_llm_allowed=false`, **When** a draft-eligible change arrives, **Then** no prompt is sent to Claude and a `llm_policy_denied` result is returned.
- **Given** `external_llm_allowed=true`, **When** budget/input validation passes, **Then** the Claude adapter may be invoked.

### [US-4] Token-budgeted prompt packing — Priority: P1
**As a** workflow operator, **I want** deterministic prompt budgets, **so that** cost and provider limits are controlled.

#### Acceptance Scenarios
- **Given** evidence/context exceeds budget, **When** packing runs, **Then** structural summary and evidence are prioritized while optional context is deterministically truncated with an omitted-context note.
- **Given** required evidence cannot fit, **When** drafting is attempted, **Then** no Claude call occurs and a budget-blocked result is returned.

### [US-5] Fake-client test seam — Priority: P1
**As an** implementer, **I want** deterministic fake Claude behavior, **so that** tests never call the real Anthropic API.

#### Acceptance Scenarios
- **Given** tests exercise the node, **When** a `FakeClaudeClient` is injected, **Then** responses and call assertions are deterministic.
- **Given** normal CI runs, **When** no explicit integration opt-in exists, **Then** real network/API calls are impossible.

### [US-6] Feature 015 node seam integration — Priority: P1
**As a** workflow maintainer, **I want** drafting to plug into Feature 015's seam, **so that** checkpointing, HITL interrupt, resume, and mutation handoff remain unchanged.

#### Acceptance Scenarios
- **Given** Feature 015 `WorkflowState`, **When** `ADRDraftNode.__call__` runs, **Then** it updates only draft outcome/content/hash/citation fields expected by that seam.
- **Given** a draft is produced, **When** workflow continues, **Then** approval/persistence/mutation are not performed by this feature.

### [US-7] Metadata-only observability — Priority: P1
**As a** platform operator, **I want** safe draft metadata, **so that** latency, policy, and budget behavior are observable without leaking prompts or drafts.

#### Acceptance Scenarios
- **Given** any draft outcome, **When** telemetry is emitted, **Then** it includes repository key, event/change ids, model id, token counts, policy state, latency, result type, and error class only.
- **Given** raw prompts, diffs, Claude responses, or pre-approval drafts exist in memory, **When** traces/logs are exported, **Then** they are excluded by default.

## Functional Requirements
- [FR-1] Consume Feature 004 `StructuralChange` and `ChangeEvidence` exactly; do not add required upstream fields or redefine semantics.
- [FR-2] Implement Feature 015's real `ADRDraftNode` seam without changing graph topology, checkpointing, HITL, or mutation handoff.
- [FR-3] Query context only through Feature 007/006 `ArchitectureContextQuery` methods.
- [FR-4] Add a `ClaudeClient` protocol, Anthropic adapter, and deterministic fake client.
- [FR-5] Enforce `RepositoryConfig.external_llm_allowed` before model egress.
- [FR-6] Enforce configurable token budget; default `8000` prompt tokens.
- [FR-7] Assemble prompts from structural change, evidence summaries, approved context citations, ADR template, and anti-injection delimiters.
- [FR-8] Validate Claude output into a provisional draft with citations, model metadata, content hash, and non-authoritative status.
- [FR-9] Return typed outcomes for no-draft, policy denied, budget exceeded, missing evidence, provider error/timeout, and invalid output.
- [FR-10] Emit metadata-only events; never export raw prompt/diff/full draft/full response by default.

## Upstream Contract Binding: Feature 004
`StructuralChange` is consumed byte-for-byte as defined in `..\004-dependency-change-detection\intent.md`:

```python
class StructuralChange:
    id: str                              # stable deterministic id
    repository: RepositoryIdentity
    source_scm_event_id: str
    provider_delivery_id: str
    normalized_pr_key: str
    change_type: Literal["dependency"]
    operation: Literal["added", "removed", "version_changed", "mixed"]
    affected_dependency: str | None
    dependency_ecosystem: str | None     # python, npm, go, rust, jvm, ruby, dotnet, unknown
    source_paths: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: float                    # 0.0..1.0
    reason_code: str                     # e.g. direct_manifest_add, manifest_lockfile_pair
    adr_recommendation: Literal["draft", "no_adr_needed"]
    classifier_name: Literal["dependency-change"]
    classifier_version: str
```

`ChangeEvidence` is consumed byte-for-byte as defined in `..\004-dependency-change-detection\intent.md`:

```python
class ChangeEvidence:
    id: str                              # stable deterministic id
    repository: RepositoryIdentity
    source_scm_event_id: str
    provider_delivery_id: str
    normalized_pr_key: str
    evidence_kind: Literal["dependency_manifest", "dependency_lockfile", "dependency_diff_summary"]
    source_path: str
    diff_hunk_ref: str | None            # reference/offset only; no raw diff export required
    before_value: str | None             # package/version/range summary when available
    after_value: str | None
    observed_operation: Literal["added", "removed", "version_changed", "lockfile_churn", "unknown"]
    parser: str
    parser_version: str
    immutable_hash: str
    summary: str                         # redaction-safe evidence summary
    provenance: dict[str, str]           # event/evidence source references only
```

## Non-Functional Requirements
- [NFR-1] Drafts are provisional and inert until downstream HITL approval.
- [NFR-2] Tests use fakes/mocks only; no live Anthropic, GitHub, graph DB, or LangSmith dependency.
- [NFR-3] Prompt packing and draft metadata are deterministic for identical inputs, excluding provider metadata.
- [NFR-4] Untrusted repository text is delimited and never treated as instructions/tools.
- [NFR-5] Adapter seams keep Anthropic SDK types out of workflow/domain logic.

## Out of Scope
Authoritative approval, reviewer UI, approval capability minting, audit durability, graph writes, GitHub publish-back, MCP serving, raw SCM fetching, and schema/API production of structural changes.

## Success Criteria
- [ ] Draft-eligible dependency changes produce provisional Markdown ADR drafts through Feature 015's draft seam.
- [ ] LLM deny policy prevents all Claude calls.
- [ ] Token budget behavior is deterministic and tested.
- [ ] Graph context is query-port-only and citation-bounded.
- [ ] Fake-client tests prove CI cannot call the real API.
- [ ] Observability is metadata-only.
- [ ] No authoritative mutations are implemented.

## Open Questions
No blocking questions remain. Autopilot defaults: prompt budget `8000`, model id configurable with default `claude-sonnet-4-6`, denied policy returns `llm_policy_denied`, draft template is Nygard/MADR-style Markdown, and normal tests never call real Anthropic APIs.
