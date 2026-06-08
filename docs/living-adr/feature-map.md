# Feature Map: LivingADR

<!-- CRISPY Project Phase: STRUCTURE → produces feature-map.md -->
<!-- Decomposes the project into FEATURES. Each feature is the unit a feature-level CRISPY run consumes. -->

**Created:** 2026-05-25
**Project:** LivingADR
**Sources:** vision.md, domain-research.md, architecture.md

---

## Feature Decomposition Rules

- Each feature is INDEPENDENTLY DELIVERABLE end-to-end.
- Features are sized to fit within a feature-level CRISPY run (3–8 vertical slices each).
- Estimated slice count per feature MUST appear in the table.
- If a feature's estimate exceeds **10 slices**, AUTO-SPLIT into sibling features (e.g., `payments-core` + `payments-refunds`) and record both rows here.
- Project-size cap: none. Surface complexity warnings but do not block.

---

## Features Overview

| ID  | Feature | Theme (vision §4) | Est. slices | Depends on | Parallelizable | Priority |
|-----|---------|-------------------|-------------|------------|----------------|----------|
| 001 | walking-skeleton-smoke | TH-01 | 5 | [] | true | P1 |
| 002 | tracked-repository-configuration | TH-07 | 5 | [] | true | P1 |
| 003 | github-webhook-ingestion | TH-01 | 6 | [002] | true | P1 |
| 004 | dependency-change-detection | TH-02 | 5 | [003] | true | P1 |
| 005 | schema-api-contract-change-detection | TH-02 | 7 | [003] | true | P1 |
| 006 | graph-store-ports-and-approval-seam | TH-04 | 6 | [002] | true | P1 |
| 007 | llamaindex-property-graph-adapter | TH-04 | 7 | [006] | true | P1 |
| 015 | workflow-orchestration-checkpointing | TH-03 | 6 | [003, 006] | true | P1 |
| 008 | claude-adr-drafting-capability | TH-03 | 7 | [004, 007, 015] | false | P1 |
| 009 | hitl-review-ui | TH-03 | 6 | [008, 015] | false | P1 |
| 010 | approval-capability-and-audit-durability | TH-03 | 7 | [009, 007, 015] | false | P1 |
| 011 | adr-publish-back-github | TH-04 | 5 | [010, 003] | false | P1 |
| 012 | mcp-context-server | TH-05 | 6 | [007, 002] | true | P1 |
| 013 | langsmith-observability-quality | TH-06 | 5 | [002] | true | P2 |
| 014 | repository-onboarding-validation | TH-07 | 4 | [002, 003] | true | P2 |

`Depends on` lists feature IDs from this same table. `Parallelizable: true` is a hint for autopilot fan-out — `crispy-project` decides waves at runtime from the dependency graph.

---

## Feature Dependency Graph (Machine-Readable)

```yaml
features:
  - id: "001"
    name: walking-skeleton-smoke
    folder: 'features\001-walking-skeleton-smoke'
    theme: TH-01
    priority: P1
    estimated_slices: 5
    depends_on: []
    parallelizable: true
    auto_split_from: null
  - id: "002"
    name: tracked-repository-configuration
    folder: 'features\002-tracked-repository-configuration'
    theme: TH-07
    priority: P1
    estimated_slices: 5
    depends_on: []
    parallelizable: true
    auto_split_from: null
  - id: "003"
    name: github-webhook-ingestion
    folder: 'features\003-github-webhook-ingestion'
    theme: TH-01
    priority: P1
    estimated_slices: 6
    depends_on: ["002"]
    parallelizable: true
    auto_split_from: null
  - id: "004"
    name: dependency-change-detection
    folder: 'features\004-dependency-change-detection'
    theme: TH-02
    priority: P1
    estimated_slices: 5
    depends_on: ["003"]
    parallelizable: true
    auto_split_from: structural-change-detection
  - id: "005"
    name: schema-api-contract-change-detection
    folder: 'features\005-schema-api-contract-change-detection'
    theme: TH-02
    priority: P1
    estimated_slices: 7
    depends_on: ["003"]
    parallelizable: true
    auto_split_from: structural-change-detection
  - id: "006"
    name: graph-store-ports-and-approval-seam
    folder: 'features\006-graph-store-ports-and-approval-seam'
    theme: TH-04
    priority: P1
    estimated_slices: 6
    depends_on: ["002"]
    parallelizable: true
    auto_split_from: graph-store-and-swap-seam
  - id: "007"
    name: llamaindex-property-graph-adapter
    folder: 'features\007-llamaindex-property-graph-adapter'
    theme: TH-04
    priority: P1
    estimated_slices: 7
    depends_on: ["006"]
    parallelizable: true
    auto_split_from: graph-store-and-swap-seam
  - id: "015"
    name: workflow-orchestration-checkpointing
    folder: 'features\015-workflow-orchestration-checkpointing'
    theme: TH-03
    priority: P1
    estimated_slices: 6
    depends_on: ["003", "006"]
    parallelizable: true
    auto_split_from: null
  - id: "008"
    name: claude-adr-drafting-capability
    folder: 'features\008-claude-adr-drafting-capability'
    theme: TH-03
    priority: P1
    estimated_slices: 7
    depends_on: ["004", "007", "015"]
    parallelizable: false
    auto_split_from: null
  - id: "009"
    name: hitl-review-ui
    folder: 'features\009-hitl-review-ui'
    theme: TH-03
    priority: P1
    estimated_slices: 6
    depends_on: ["008", "015"]
    parallelizable: false
    auto_split_from: hitl-approval-workflow
  - id: "010"
    name: approval-capability-and-audit-durability
    folder: 'features\010-approval-capability-and-audit-durability'
    theme: TH-03
    priority: P1
    estimated_slices: 7
    depends_on: ["009", "007", "015"]
    parallelizable: false
    auto_split_from: hitl-approval-workflow
  - id: "011"
    name: adr-publish-back-github
    folder: 'features\011-adr-publish-back-github'
    theme: TH-04
    priority: P1
    estimated_slices: 5
    depends_on: ["010", "003"]
    parallelizable: false
    auto_split_from: null
  - id: "012"
    name: mcp-context-server
    folder: 'features\012-mcp-context-server'
    theme: TH-05
    priority: P1
    estimated_slices: 6
    depends_on: ["007", "002"]
    parallelizable: true
    auto_split_from: null
  - id: "013"
    name: langsmith-observability-quality
    folder: 'features\013-langsmith-observability-quality'
    theme: TH-06
    priority: P2
    estimated_slices: 5
    depends_on: ["002"]
    parallelizable: true
    auto_split_from: null
  - id: "014"
    name: repository-onboarding-validation
    folder: 'features\014-repository-onboarding-validation'
    theme: TH-07
    priority: P2
    estimated_slices: 4
    depends_on: ["002", "003"]
    parallelizable: true
    auto_split_from: null
```

Every feature in the overview table MUST appear here exactly once.

---

## Per-Feature Briefs

<!-- 1 paragraph per feature: enough for the feature-level Clarify phase to start with context, NOT a full spec. -->

### 001 · walking-skeleton-smoke

Deliver the thinnest visible LivingADR path: replay or receive one merged-PR-like event, classify it with a deterministic stub, create a minimal `ADRDraft`, accept it through a stubbed HITL action, persist a stub `ADRRecord`, and answer one MCP-style "why" query from seeded approved context. This is the walking-skeleton candidate because it crosses `workflow-service`, graph persistence, HITL, and `mcp-context-server` without waiting for production classifiers or Claude quality; relevant architecture anchors are `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#deployment`, and `architecture.md#anti-patterns`, and it validates TH-01 through TH-05 at smoke-test depth.

### 002 · tracked-repository-configuration

Implement `living-adr.config.yaml` loading, `RepositoryIdentity` and `RepositoryConfig` validation, startup error reporting, publication-policy parsing, external-LLM allow/deny flags, restart-required lifecycle semantics, and the thin no-op `Observability` core port/interface for the 1-repo PoC while treating N≥1 uniformly. This is the foundational configuration seam for GitHub ingestion, Claude egress policy, graph scoping, MCP filtering, publish-back, and later instrumentation; `013` swaps the LangSmith implementation behind this early port rather than defining the port late. Relevant architecture anchors are `architecture.md#data-model`, `architecture.md#cross-cutting`, `architecture.md#repositories`, and `architecture.md#deployment`, covering TH-07 with MVP-critical priority.

### 003 · github-webhook-ingestion

Build the GitHub App webhook entry path for merged PRs: HMAC verification, delivery-id idempotency, normalized `SCMEvent` creation, minimal PR/diff fetch handles through the `SCMProvider`/`GitHubProvider` adapter, replay/dead-letter state, and a candidate evidence stream for downstream structural-change classifiers. The feature should preserve Azure DevOps as a future adapter while staying GitHub-first; relevant architecture anchors are `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#anti-patterns`, especially FM-17, FM-18, and FM-24.

### 004 · dependency-change-detection

Detect new dependency changes from merged PR evidence and normalize them into `StructuralChange` plus immutable `ChangeEvidence` records with confidence, source file paths, and no-ADR-needed outcomes when the signal is below threshold. This child of the oversized structural-change-detection feature focuses on dependency manifests and package-lock style evidence so it can ship independently before schema/API classifiers; relevant architecture anchors are `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#anti-patterns`, reflecting TH-02 and FM-03/FM-06.

### 005 · schema-api-contract-change-detection

Detect database/schema changes and API contract changes from merged PR evidence, producing `StructuralChange` classifications with evidence summaries, confidence, and explicit uncertainty where runtime or generated artifacts limit static certainty. This child of structural-change-detection is larger because it must handle two MVP trigger classes and keep API/schema semantics distinct; relevant architecture anchors are `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#anti-patterns`, especially FM-07 and the open threshold question in `architecture.md#anti-patterns`/§10.

### 006 · graph-store-ports-and-approval-seam

Define the stable write/read ports (`ArchitectureGraphStore`, `ArchitectureContextQuery`), core graph value objects, `ADRRecordRepository` expectations, adapter conformance surface, and `ApprovalBoundMutationService` contract that makes graph mutation impossible without `ApprovedReviewDecision`. This child of graph-store-and-swap-seam deliberately ships the swap seam before the LlamaIndex adapter so workflows, HITL, and MCP depend on typed ports rather than implementation details; relevant architecture anchors are `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#anti-patterns`.

### 007 · llamaindex-property-graph-adapter

Implement the default `LlamaIndexPropertyGraphAdapter` behind the graph ports with repository-scoped nodes, schema version metadata, SQLite/WAL-compatible persistence under `var\graph`, conformance tests, provenance on extracted entities/edges, and read snapshots suitable for the MCP server. This child of graph-store-and-swap-seam is the primary TH-04 storage/retrieval adapter and mitigates property-graph drift and false edges; relevant architecture anchors are `architecture.md#tech-stack`, `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#deployment`.

### 015 · workflow-orchestration-checkpointing

Assemble the production LangGraph workflow state machine for intake → structural-change classification → ADR draft → HITL interrupt/resume → approved mutation, including SQLite-backed checkpointer persistence, replay/recovery hooks, and stub-node seams for classifier, drafting, and HITL phases while downstream production nodes are still landing. It depends on `003` for the normalized `SCMEvent` intake contract and `006` for graph/mutation ports, with repository config available transitively through those foundations; this keeps orchestration durable without depending on concrete classifier/draft/UI implementations or introducing graph cycles. Relevant architecture anchors are `architecture.md#tech-stack`, `architecture.md#service-boundaries`, `architecture.md#data-model`, and `architecture.md#cross-cutting`, especially the LangGraph orchestration role split, SQLite checkpointer durability, FM-01, and FM-17 replay/recovery.

### 008 · claude-adr-drafting-capability

Create the `ClaudeClient` adapter, prompt/evidence packaging, token-budget enforcement, per-repository external-LLM allow/deny behavior, fake-client test seam, and `ADRDraft` generation from approved structural-change candidates plus relevant existing graph context. It should produce a human-readable Markdown ADR draft with evidence, alternatives, consequences, and provisional-rationale labeling, without performing authoritative mutations; `004` supplies the first MVP `StructuralChange` producer, while `005` integrates later as a follow-on producer of the same abstraction rather than blocking dependency-change ADRs from reaching HITL/publish. Relevant architecture anchors are `architecture.md#tech-stack`, `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#anti-patterns`, addressing TH-03 and FM-04/FM-06/FM-14/FM-19.

### 009 · hitl-review-ui

Build the server-rendered FastAPI/Jinja2 review surface for pending `ADRDraft` items with evidence citations, confidence, alternatives/consequences, approve/edit/reject actions, semantic HTML, keyboard accessibility, and single-user PoC token protection. This child of hitl-approval-workflow keeps UI and reviewer ergonomics separate from capability enforcement while making approval meaningful rather than rubber-stamped; relevant architecture anchors are `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#anti-patterns`, especially FM-20 and accessibility guidance.

### 010 · approval-capability-and-audit-durability

Implement durable `ApprovalEvent` recording, `ApprovedReviewDecision` minting and one-shot consumption, TTL expiry, draft content-hash pinning, idempotent retry semantics, mutation/audit linkage, and rejection/edit lifecycle state so SM-05 remains enforceable. This child of hitl-approval-workflow consumes the UI decision and the graph adapter through `ApprovalBoundMutationService`; relevant architecture anchors are `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#anti-patterns`, especially the approved-mutation boundary and FM-13/FM-23.

### 011 · adr-publish-back-github

When `RepositoryConfig.adr_publication_policy` requires publication, commit an approved Markdown `ADRRecord` to the configured `docs\adr\NNNN-<slug>.md` path and target branch through GitHub App credentials, preserving `decision_id` audit linkage and making direct-commit versus PR publication a feature-level design choice. This feature depends on approved decisions and GitHub SCM access but remains optional by policy; relevant architecture anchors are `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#anti-patterns`, reflecting docs-as-code review-gate risks.

### 012 · mcp-context-server

Implement the read-only `mcp-context-server` process using the official Python MCP SDK, `ArchitectureContextQuery`, repository scoping, stdio transport for PoC, minimal local trust/auth assumptions, and tools/resources for `answer_why`, `fetch_adr`, and `list_adrs` with citations to approved ADRs. The feature deliberately excludes write operations, SCM credentials, and broad IDE extension UX; relevant architecture anchors are `architecture.md#tech-stack`, `architecture.md#service-boundaries`, `architecture.md#data-model`, `architecture.md#cross-cutting`, and `architecture.md#deployment`, addressing TH-05 and FM-11/FM-12/FM-15/FM-16.

### 013 · langsmith-observability-quality

Swap the early no-op `Observability` port from `002` to the LangSmith-backed implementation, adding structured logs, metadata-only traces, default-deny raw export controls, latency and token-count metrics, draft acceptance/rejection tracking, unauthorized-mutation checks, and a small evaluation harness for retrieval and drafting regression signals. This TH-06 feature depends only on the foundational port so it can remain lightweight and integrate feature-by-feature without forcing every instrumented capability to depend on LangSmith directly; relevant architecture anchors are `architecture.md#tech-stack`, `architecture.md#cross-cutting`, `architecture.md#data-model`, and `architecture.md#anti-patterns`, especially FM-21/FM-22 and reviewer notes on SM-01 through SM-05 instrumentation.

### 014 · repository-onboarding-validation

Provide the PoC onboarding path for adding or verifying the single tracked repository: CLI or documented startup checks, GitHub App installation verification, config validation messages, `.env.example` alignment, and operator-facing diagnostics without creating multi-repo governance automation. This P2 TH-07 feature hardens adoption after the MVP path exists while avoiding hot reload and broad rollout; relevant architecture anchors are `architecture.md#repositories`, `architecture.md#data-model`, `architecture.md#cross-cutting`, `architecture.md#deployment`, and `architecture.md#anti-patterns`.

---

## Auto-Split Log

<!-- One entry per feature created via the >10-slice auto-split heuristic. -->

| Original theme | Split into | Reason |
|----------------|------------|--------|
| structural-change-detection | dependency-change-detection (004) | Structural-change-detection was estimated at 12 slices; dependency detection is isolated from schema/API semantics so it can ship independently. |
| structural-change-detection | schema-api-contract-change-detection (005) | Structural-change-detection was estimated at 12 slices; schema and API-contract detection remain together because they share contract/evidence parsing concerns. |
| graph-store-and-swap-seam | graph-store-ports-and-approval-seam (006) | Graph-store-and-swap-seam was estimated at 13 slices; stable ports and approval-bound mutation semantics must land before any concrete adapter. |
| graph-store-and-swap-seam | llamaindex-property-graph-adapter (007) | Graph-store-and-swap-seam was estimated at 13 slices; LlamaIndex persistence, provenance, schema versioning, and conformance are a separate adapter risk center. |
| hitl-approval-workflow | hitl-review-ui (009) | HITL-approval-workflow was estimated at 13 slices; review UX and accessibility should be delivered separately from capability enforcement. |
| hitl-approval-workflow | approval-capability-and-audit-durability (010) | HITL-approval-workflow was estimated at 13 slices; content hashing, one-shot capabilities, expiry, idempotency, and audit durability form the enforcement half. |

---

## Risk & Complexity Notes

- **Walking-skeleton candidate:** 001 `walking-skeleton-smoke`; it has no dependencies and should be the Phase 5 first milestone candidate because it yields visible end-to-end value across webhook/replay, draft, review, graph, and MCP read stubs.
- **Highest-complexity features:** 005 `schema-api-contract-change-detection`, 007 `llamaindex-property-graph-adapter`, 008 `claude-adr-drafting-capability`, 010 `approval-capability-and-audit-durability`, and 015 `workflow-orchestration-checkpointing` carry the highest ambiguity and should receive feature-level clarify/review attention.
- **Cross-feature integration risks:** preserve the source-of-truth hierarchy from `architecture.md#cross-cutting`: code/PR data is evidence, ADRs are approved rationale, and graph nodes are projections; do not allow Claude output, MCP tools, or publish-back to bypass `ApprovedReviewDecision`.
- **Domain failure modes driving risk:** FM-06 hallucinated rationale, FM-08/FM-10 graph drift and false edges, FM-15/FM-16 MCP trust/auth mismatch, FM-17 webhook replay complexity, FM-20 approval fatigue, FM-21 trace leakage, and FM-23 docs-as-code without review gates should be carried into feature-level specs.
- **Dependency shape:** longest chain remains 7 features by node count (`002 → 003 → 004 → 008 → 009 → 010 → 011`, `002 → 003 → 015 → 008 → 009 → 010 → 011`, or `002 → 006 → 007 → 008 → 009 → 010 → 011`); largest natural fan-out wave is 5 features once ingestion and graph-port foundations land (`004`, `005`, `007`, `014`, `015`). Feature `005` still ships as schema/API coverage, but it is now a follow-on `StructuralChange` producer rather than a build blocker for the first dependency-change ADR through `008`.
- **Soft warning thresholds tripped:** none. Feature count is 15 (≤15), and the auto-split rule fired on 3 oversized candidates (≤4).
- **Known open questions to carry forward:** exact GitHub App permissions and local webhook delivery path, held-out query/evaluation rubric for SM-03/SM-04, confidence thresholds per classifier, direct commit vs PR publish-back policy, and post-PoC MCP HTTP/auth and SQLite migration triggers.

---

## Reviewer Findings

- **Finding 1 — orchestration ownership:** Resolved by adding 015 `workflow-orchestration-checkpointing` as the production owner of LangGraph graph assembly, SQLite checkpointer persistence, and HITL interrupt/resume wiring. Features 008, 009, and 010 now depend on 015 so their concrete nodes/phases plug into the durable workflow backbone.
- **Finding 2 — 008 over-constrained fan-in:** Resolved by relaxing 008 from `[004, 005, 007]` to `[004, 007, 015]`. Feature 004 can drive the first dependency-change ADR end to end; 005 remains a P1 follow-on producer of the same `StructuralChange`/`ChangeEvidence` abstraction.
- **Finding 3 — observability port unassigned:** Resolved by assigning the no-op `Observability` core port/interface to 002 and making 013 depend on 002 as the LangSmith implementation behind that port, without adding broad observability edges to every instrumented feature.
