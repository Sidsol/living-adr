# Project Roadmap: LivingADR

| Field | Value |
|---|---|
| **Created** | 2026-05-29 |
| **Project** | LivingADR |
| **Sources** | vision.md, architecture.md, feature-map.md |
| **Note** | No calendar dates — sequencing only. |

This roadmap sequences the 15 feature-map features into outcome-oriented milestones and dependency-derived parallelization waves. The feature-map is the authoritative dependency source.

---

## 1. Milestones

### M1 — Walking Skeleton

**Goal:** Prove the thinnest visible LivingADR path across replay/ingestion, draft, stubbed review, stubbed graph persistence, and MCP-style readback.

**Features:**

| ID | Feature | Theme | Priority |
|---|---|---|---|
| 001 | walking-skeleton-smoke | TH-01 | P1 |

**Vision / MVP value unlocked:** Smoke-test depth validation across TH-01 through TH-05: event trigger, structural classification stub, ADR review stub, connected context stub, and queryable answer path. This is the walking-skeleton candidate called out in `feature-map.md` Risk & Complexity Notes.

**Exit criterion:** A replayed or received merged-PR-like event produces a minimal ADR draft, accepts it through stub HITL, persists a stub approved ADR record, and answers one seeded "why" query through an MCP-style path.

**Risk notes:** Keep scope deliberately thin; production classifiers, Claude quality, durable approval enforcement, and real graph semantics come later.

---

### M2 — Core Foundations

**Goal:** Establish repository configuration, GitHub merged-PR intake, and graph/approval ports that every production path depends on.

**Features:**

| ID | Feature | Theme | Priority |
|---|---|---|---|
| 002 | tracked-repository-configuration | TH-07 | P1 |
| 003 | github-webhook-ingestion | TH-01 | P1 |
| 006 | graph-store-ports-and-approval-seam | TH-04 | P1 |

**Vision / MVP value unlocked:** Enables the GitHub-first PoC boundary, repository-scoped configuration, replayable event intake, and the approval-bound graph mutation seam required by SM-05.

**Exit criterion:** `living-adr.config.yaml` loads and validates the PoC repo; GitHub merged-PR events are verified, normalized, idempotent, and replayable; workflow/HITL/MCP code can depend on stable graph/query and approval-bound mutation ports.

**Risk notes:** These features define source-of-truth and trust boundaries. Review SCM event normalization, repository scoping, and mutation-impossible-without-approval semantics before downstream implementation fans out.

---

### M3 — Detection, Graph Adapter, and Orchestration Backbone

**Goal:** Add production structural-change producers, the default graph adapter, and durable LangGraph orchestration so draft/review/publish features have real seams to plug into.

**Features:**

| ID | Feature | Theme | Priority |
|---|---|---|---|
| 004 | dependency-change-detection | TH-02 | P1 |
| 005 | schema-api-contract-change-detection | TH-02 | P1 |
| 007 | llamaindex-property-graph-adapter | TH-04 | P1 |
| 015 | workflow-orchestration-checkpointing | TH-03 | P1 |

**Vision / MVP value unlocked:** Covers the structural-change and connected-knowledge core for the first ADR flow: new dependency detection can drive the first end-to-end ADR, while schema/API detection broadens MVP trigger coverage.

**Exit criterion:** Dependency changes produce `StructuralChange` / `ChangeEvidence`; schema/API changes produce compatible follow-on classifications; the LlamaIndex adapter passes graph-port conformance with repository scoping and provenance; the LangGraph workflow durably checkpoints intake through HITL interrupt/resume seams.

**Risk notes:** High-complexity features 005, 007, and 015 need early feature-level clarify/review. Feature 005 is a P1 follow-on producer and is not a blocker for the first dependency-change ADR through drafting and HITL.

---

### M4 — First End-to-End ADR and MCP Context Delivery

**Goal:** Deliver the MVP user outcome: an approved ADR from a qualifying merged PR is drafted, reviewed, durably authorized, optionally published back to GitHub, and answerable through the read-only MCP context server.

**Features:**

| ID | Feature | Theme | Priority |
|---|---|---|---|
| 008 | claude-adr-drafting-capability | TH-03 | P1 |
| 009 | hitl-review-ui | TH-03 | P1 |
| 010 | approval-capability-and-audit-durability | TH-03 | P1 |
| 011 | adr-publish-back-github | TH-04 | P1 |
| 012 | mcp-context-server | TH-05 | P1 |

**Vision / MVP value unlocked:** Completes TH-03, TH-04, and TH-05 for the PoC: human-reviewed ADR drafting, approved authoritative mutation, GitHub ADR publication when policy requires it, and cited "why" answers for developers/AI assistants. This makes SM-01, SM-02, and SM-05 demonstrable at the MVP cut; SM-03 and SM-04 require the held-out query/evaluation harness in M5 feature 013.

**Exit criterion:** A dependency-change merged PR can generate a Claude ADR draft, present evidence to the reviewer, accept approve/edit/reject, mint and consume an approved capability, persist/audit the approved ADR and graph projection, publish Markdown to the configured GitHub path when enabled, and answer an MCP `answer_why` query with citations.

**Risk notes:** High-complexity features 008 and 010 sit on the schedule-driving chain and require strong review around prompt injection, provisional rationale, content-hash pinning, one-shot capabilities, audit linkage, and unauthorized mutation prevention.

---

### M5 — Operational and Onboarding Hardening

**Goal:** Add P2 quality and onboarding support that improves trust and adoption without blocking the first end-to-end ADR.

**Features:**

| ID | Feature | Theme | Priority |
|---|---|---|---|
| 013 | langsmith-observability-quality | TH-06 | P2 |
| 014 | repository-onboarding-validation | TH-07 | P2 |

**Vision / MVP value unlocked:** Strengthens SM-01 and SM-02 measurement, adds the held-out query/evaluation harness needed for SM-03 and SM-04, improves SM-05 monitoring, trace hygiene, and PoC repository setup diagnostics. These features are foundational hardening but can trail the first end-to-end ADR if needed.

**Exit criterion:** LangSmith-backed observability captures metadata-only traces, latency/token/decision metrics, rejection and unauthorized-mutation signals, and a small evaluation harness; repository onboarding validates GitHub App installation, config, `.env.example`, and operator diagnostics for the single PoC repo.

**Risk notes:** Keep raw export default-deny and onboarding scoped to the PoC; broad multi-repo governance, hot reload, and enterprise rollout remain post-PoC.

---

## 2. Parallelization Waves

Derived from the machine-readable dependency graph in `feature-map.md`. The architecture has one repo, `living-adr`; at roadmap granularity these waves remain fleet-eligible when multiple features touch different package areas or can coordinate through stable ports. Feature-level manifests should further split any same-area file conflicts.

1. **W0:** [001, 002] — fleet-eligible.
2. **W1:** [003, 006, 013] — fleet-eligible.
3. **W2:** [004, 005, 007, 014, 015] — fleet-eligible; largest fan-out.
4. **W3:** [008, 012] — fleet-eligible.
5. **W4:** [009] — serial.
6. **W5:** [010] — serial.
7. **W6:** [011] — serial.

This confirms the provided topological sequencing. P2 features 013 and 014 are dependency-ready early but may be deferred to M5 as hardening if MVP pressure requires it.

---

## 3. Critical Path

**Longest dependency chain length:** 7 feature nodes.

Representative critical chains from `feature-map.md`:

- 002 → 003 → 004 → 008 → 009 → 010 → 011
- 002 → 003 → 015 → 008 → 009 → 010 → 011
- 002 → 006 → 007 → 008 → 009 → 010 → 011

The schedule-driving path runs through configuration, ingestion or graph foundations, drafting, HITL, approval durability, and publish-back. High-complexity features 007, 008, 010, and 015 are on critical paths; 005 is high-complexity but near-path/fan-out work and not a blocker for the first dependency-change ADR.

---

## 4. Risk-Front-Loading and Sequencing Rationale

- Start with 001 to validate the selected two-process architecture and end-to-end product loop before investing in production quality.
- Land 002, 003, and 006 before broad fan-out because repository scoping, SCM normalization, and approval-bound graph ports are shared contracts.
- Front-load clarify/review for 005, 007, 008, 010, and 015. They carry graph drift, orchestration durability, prompt/rationale quality, HITL enforcement, and auditability risks.
- Treat 005 as a P1 follow-on `StructuralChange` producer: it expands schema/API trigger coverage but does not block a first dependency-change ADR through 008 → 009 → 010 → 011.
- Keep 013 and 014 visible as early dependency-ready hardening but allow them to trail the MVP cut if needed.

---

## 5. MVP Cut Line

**MVP completes at:** **M4 — First End-to-End ADR and MCP Context Delivery**.

MVP means a qualifying merged PR in the configured single GitHub repository can produce an approved ADR end to end, publish/store approved rationale, and answer an MCP "why" query with citations. At the M4 cut, this demonstrates SM-01 draft acceptance tracking, SM-02 PR-to-draft latency, and SM-05 unauthorized-mutation prevention. SM-03 retrieval relevance and SM-04 architecture question coverage require the held-out query set/evaluation harness delivered by M5 feature 013.

**Post-MVP hardening:** M5 features 013 and 014, plus any deferred portions of broad observability dashboards, evaluation-rubric expansion, onboarding ergonomics, multi-repo governance, hot reload, HTTP/OAuth MCP, Azure DevOps, advanced retrieval ranking, and SQLite-to-server-store migration.

---

## 6. Cross-Repo Coordination

| Repo | Features touching it | Coordination notes |
|---|---|---|
| `living-adr` | 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 015 | Single local repo with two deployables: `workflow-service` and `mcp-context-server`. Use package-area ownership (`core`, `scm`, `graph`, `workflow`, `hitl`, `observability`, app entry points) to avoid same-wave file conflicts; stabilize ports before dependent adapters/UI. |

---

## 7. Machine-Readable Summary

```yaml
milestones:
  - id: M1
    name: Walking Skeleton
    features: ["001"]
  - id: M2
    name: Core Foundations
    features: ["002", "003", "006"]
  - id: M3
    name: Detection, Graph Adapter, and Orchestration Backbone
    features: ["004", "005", "007", "015"]
  - id: M4
    name: First End-to-End ADR and MCP Context Delivery
    features: ["008", "009", "010", "011", "012"]
  - id: M5
    name: Operational and Onboarding Hardening
    features: ["013", "014"]
waves:
  - ["001", "002"]
  - ["003", "006", "013"]
  - ["004", "005", "007", "014", "015"]
  - ["008", "012"]
  - ["009"]
  - ["010"]
  - ["011"]
critical_path:
  length_nodes: 7
  examples:
    - ["002", "003", "004", "008", "009", "010", "011"]
    - ["002", "003", "015", "008", "009", "010", "011"]
    - ["002", "006", "007", "008", "009", "010", "011"]
mvp_milestone: M4
post_mvp_hardening: ["013", "014"]
```
