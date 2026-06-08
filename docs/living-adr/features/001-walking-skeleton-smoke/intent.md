# Architecture Intent: walking-skeleton-smoke

## Current State
The implementation repository `C:\repos\living-adr` is not present yet. The authoritative design calls for one Python repo with shared packages and two deployables: `workflow-service` and `mcp-context-server` (`..\..\architecture.md#repositories`, `..\..\architecture.md#service-boundaries`). The architecture already defines the critical data model (`..\..\architecture.md#data-model`), local deployment constraints (`..\..\architecture.md#deployment`), and anti-patterns to avoid (`..\..\architecture.md#anti-patterns`).

## Desired State
Feature 001 creates a smoke-depth walking skeleton that proves the visible path:

`merged-PR-like replay fixture -> SCMEvent -> stub StructuralChange/ChangeEvidence -> minimal ADRDraft -> stub HITL accept -> approval-bound ADRRecord persistence -> MCP-style answer_why from approved context`.

The desired state is explicitly stubbed. It must not implement production GitHub ingestion, Claude drafting, full HITL UI, LlamaIndex graph semantics, or production MCP conformance.

## Gap Analysis

| Area | Current | Desired | Gap |
|---|---|---|---|
| Repo scaffold | `living-adr` repo absent | Minimal architecture-aligned package layout | Create initial files per `..\..\architecture.md#tech-stack` without overbuilding. |
| Event intake | No implementation | Deterministic merged-PR-like replay fixture | Add fixture and replay entrypoint that emits one repository-scoped `SCMEvent`. |
| Classification | No implementation | Stub deterministic `StructuralChange` and `ChangeEvidence` | Add fake classifier with explicit smoke labeling. |
| Drafting | No implementation | Minimal provisional `ADRDraft` | Add renderer that cites fixture evidence and avoids Claude. |
| HITL | No implementation | Stub accept action | Add review decision object with draft hash and repository scope. |
| Persistence | No implementation | Stub approved `ADRRecord` and projection | Add approval-bound store that rejects missing decision. |
| MCP read | No implementation | Read-only `answer_why` from approved context | Add MCP-style query path depending on read port only. |

## Architecture Options

### Option A: Single script smoke demo
**Approach:** Put the entire event -> answer path in one executable script with in-memory data.
- ✅ Pros: Fastest to build; easy to demonstrate; minimal files.
- ❌ Cons: Does not exercise service/package seams; risks becoming throwaway code that proves little about the architecture.
- 🔧 Effort: Low

### Option B: Full production-shaped services with stubs behind ports
**Approach:** Create the planned package layout, two app entry points, domain models, port-shaped interfaces, and stub implementations for SCM/classifier/HITL/graph/MCP.
- ✅ Pros: Exercises the real boundaries in `..\..\architecture.md#service-boundaries`; supports later replacement of stubs; makes approval seam testable.
- ❌ Cons: More files than a script; risk of prematurely freezing contracts before downstream feature specs.
- 🔧 Effort: Medium

### Option C: Wait for foundational features 002/003/006/012
**Approach:** Defer the walking skeleton until repository configuration, GitHub ingestion, graph ports, and MCP server are production-planned/implemented.
- ✅ Pros: Avoids temporary stubs; less rework.
- ❌ Cons: Violates M1 goal; delays architectural risk discovery; provides no early end-to-end proof.
- 🔧 Effort: Low now, high later

## Selected Approach
**Option B: Full production-shaped services with stubs behind ports**

Rationale: The feature exists to prove seams, not production intelligence. A single script would not validate the two-deployable architecture, while waiting would defeat the roadmap's M1 risk-front-loading. Option B gives a thin but meaningful path across `workflow-service`, HITL, approval-bound persistence, and `mcp-context-server` while keeping all non-production behavior explicitly named as smoke stubs.

## Approval-Bound Mutation and Source-of-Truth Discipline
This feature must respect the architecture even while stubbed:

- `ADRDraft` remains provisional and is never read as authoritative context.
- The stub HITL accept action must create an `ApprovedReviewDecision`-shaped object with repository scope and draft hash.
- The stub persistence service must reject `ADRRecord` creation if the approved decision is absent or mismatched.
- MCP-style `answer_why` must read only approved `ADRRecord` data, never pending drafts or raw fixture evidence as rationale.
- Code/PR fixture data is evidence; approved ADR record is authoritative rationale; graph/query structures are projections with citations, matching `..\..\architecture.md#data-model` and `..\..\architecture.md#anti-patterns`.

## Module Surface Analysis

| Module | Inputs | Callers | Deletion Test | Isolated-Test Candidate |
|---|---:|---|---|---|
| `workflow.smoke_fixture` | 0 external, fixture constants | workflow app, tests | Deleting breaks replay only | Yes: deterministic fixture normalization. |
| `workflow.smoke_flow` | fixture, classifier, reviewer, store | workflow app, smoke test | Deleting removes E2E path | Yes: pure orchestrator with fake dependencies. |
| `hitl.stub_review` | `ADRDraft`, reviewer id | smoke flow, tests | Deleting prevents approval | Yes: stable input/output and hash behavior. |
| `graph.stub_store` | `ADRRecord`, decision | smoke flow, MCP query, tests | Deleting removes persistence/query projection | Yes: approval guard and approved-only reads. |
| `apps.mcp_context_server.main` | repository, question, code area | smoke query CLI/test | Deleting removes MCP-style readback | Yes if kept as function wrapper over query port. |

## Anti-Patterns to Avoid
- **Script-only success:** Tempting for speed, but it bypasses service boundaries and weakens the walking-skeleton proof.
- **Stub becomes production contract:** Stubs must be named and documented as smoke-only so later features can replace them.
- **Draft-as-authority shortcut:** Reading `ADRDraft` directly in the MCP answer would violate source-of-truth hierarchy.
- **Mutation without approval for convenience:** Even stub persistence must reject missing `ApprovedReviewDecision` to preserve SM-05 intent.
- **Hidden external calls:** No GitHub, Claude, LangSmith, LlamaIndex network/service, or remote MCP dependency in the smoke path.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Create initial Python package layout and smoke-depth modules/tests. | High |
| `crispy-docs` | Planning artifacts only in this feature folder. | High |

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Stubs accidentally imply production completeness | Medium | High | Use `smoke`/`stub` names, docstrings, test names, and explicit out-of-scope notes. |
| Approval seam diluted for speed | Medium | High | Write guard tests before persistence implementation; require decision-shaped object. |
| Too much scaffold work obscures feature | Medium | Medium | Create only files needed by smoke path and tests. |
| Later features need different interfaces | Medium | Medium | Keep interfaces local/port-shaped but minimal; avoid broad abstract base classes until feature 006. |
| MCP-style function differs from final SDK | High | Low | Encapsulate read behavior behind `answer_why` wrapper; final feature 012 can replace transport. |
