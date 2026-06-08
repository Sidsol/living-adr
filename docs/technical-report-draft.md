# LivingADR — Technical Report (Draft)

> **Status:** Draft · **Scope of this draft:** Sections 1–3 are fully developed
> (Problem & business context, Architecture & framework rationale, Implementation
> progress & validation evidence). Sections 4–7 are outlined for completion in the
> next revision.
> **System under report:** LivingADR proof-of-concept (PoC), tracking the
> repository `github.com/Sidsol/living-adr` (the system captures decisions about
> *itself* — i.e., it is dogfooded).
> **Quality bar at time of writing:** 880 automated tests passing; linter clean.

## Table of contents

1. [Problem Statement and Business Justification](#1-problem-statement-and-business-justification)
2. [Architecture Decisions and Framework Rationale](#2-architecture-decisions-and-framework-rationale)
3. [Implementation Progress and Validation Evidence](#3-implementation-progress-and-validation-evidence)
4. [Model Selection and Benchmark Evidence](#4-model-selection-and-benchmark-evidence-outline) *(outline)*
5. [RAG / Reasoning Pipeline Design](#5-rag--reasoning-pipeline-design-outline) *(outline)*
6. [Responsible AI Analysis (Risks and Mitigations)](#6-responsible-ai-analysis-risks-and-mitigations-outline) *(outline)*
7. [Lessons Learned and Future Work](#7-lessons-learned-and-future-work-outline) *(outline)*
- [Appendix A — Glossary](#appendix-a--glossary)
- [Appendix B — Technology summary](#appendix-b--technology-summary)

---

## 1. Problem Statement and Business Justification

### 1.1 The problem: architectural knowledge decays

Software systems accrue *architecture-significant decisions* continuously: a new
dependency is adopted, an API contract changes, a schema is altered, a boundary
is moved. The **rationale** for each decision — the context, the alternatives
weighed, the consequences accepted — is the most valuable and the most perishable
artifact a team produces. In practice that rationale is captured, if at all, in:

- a pull-request description or review thread that is never read again,
- a chat message that scrolls away,
- or an individual's memory that leaves when they do.

Architecture Decision Records (ADRs) are the established remedy, but they share a
fatal operational weakness: **they depend on a human remembering to write and
maintain them at exactly the moment they are least inclined to.** The result is
predictable and costly:

- **Knowledge decay / tribal knowledge.** Settled decisions are silently
  re-opened and re-litigated because no durable, discoverable record exists.
- **Onboarding friction.** New engineers (and contractors) cannot answer "why is
  it built this way?" without interrupting senior staff.
- **Architectural drift.** Without an authoritative record, local changes
  accumulate into unintended global change.
- **Ungrounded AI assistance.** AI coding assistants are now ubiquitous, but they
  reason from code *as it is*, not from *why it is that way*. Lacking authoritative
  architectural context, they confidently reinforce drift and hallucinate
  rationale.

### 1.2 Why now

Two trends make this the right time to solve the problem with automation:

1. **AI assistants have moved into the critical path of software change.** Their
   suggestions are only as good as the context they are grounded in. An
   authoritative, citable store of *approved* architectural decisions is exactly
   the grounding they lack — and the Model Context Protocol (MCP) now provides a
   standard way to deliver it into IDEs and agents.
2. **LLMs are good enough to draft, not to decide.** Modern models can reliably
   turn a diff plus structured evidence into a well-formed ADR *draft*. They are
   not trustworthy enough to make or publish an architectural decision
   unsupervised. This asymmetry — capable drafter, untrustworthy decider — defines
   the product: **automate the drafting, keep the human as the approver.**

### 1.3 Proposed solution

**LivingADR** automatically drafts an ADR from every merged pull request that
contains an architecture-significant change, routes the draft through a
lightweight human approval, stores the approved decision in a queryable property
graph, and publishes it back into the repository as a pull request. A companion
**read-only** server exposes the approved decisions to IDEs and AI assistants over
MCP, with citations back to source evidence.

The design principle is **"capture at the moment of decision, with a human in the
loop."** The cost of capture is paid automatically at merge time; the human cost
is reduced to an approve/reject review of a pre-written draft.

### 1.4 Business justification

| Driver | Mechanism | Outcome |
|---|---|---|
| **Faster onboarding** | New hires/agents query `answer_why` instead of interrupting seniors | Reduced ramp time; less senior-engineer interruption |
| **Less rework** | Settled decisions are discoverable and cited | Fewer re-litigated decisions; less architectural churn |
| **Governance & audit** | Every approved write is bound to a one-shot, human approval and recorded in an append-only audit trail | Defensible, traceable decision history |
| **Grounded AI** | MCP serves *approved* decisions with citations | Fewer hallucinated rationales; assistants respect existing constraints |
| **Low marginal cost** | Drafting is automated at merge; humans only review | Capture happens even when no one would have written an ADR by hand |

### 1.5 Stakeholders and success criteria

**Stakeholders:** software engineers (authors/reviewers), technical leads and
architects (approvers, governance), new joiners and contractors (consumers), and
AI assistants / IDEs (programmatic consumers).

**Success criteria for the PoC:**

- ADRs are **drafted automatically** from merged PRs without author effort.
- A human **approves** before anything becomes authoritative or is published.
- Approved decisions are **queryable with citations** back to the originating
  evidence.
- The system is **safe by construction**: no authoritative write without a valid,
  one-shot human approval; the read path cannot mutate state.

### 1.6 Scope and non-goals (PoC)

In scope: a **single tracked repository** (`github.com/Sidsol/living-adr`), the
end-to-end loop from merged PR to published ADR, and read-only context serving.

Explicit non-goals for the PoC: multi-repository governance and fan-out,
repository discovery, hot configuration reload, and production-grade hosting with
automatic supervision. These are deferred to *Future Work* (Section 7).

---

## 2. Architecture Decisions and Framework Rationale

### 2.1 System overview

LivingADR is split into two independently deployable services along a strict
**write/read boundary**:

- **`workflow-service`** (`living-adr-workflow`) — the *write path*: receives
  GitHub webhooks, fetches evidence, drafts the ADR, hosts the human review UI,
  performs the approval-bound graph write, and publishes the ADR PR.
- **`mcp-context-server`** (`living-adr-mcp`) — the *read path*: a **read-only**
  MCP server that serves approved decisions to IDEs/agents. It is read-only *by
  construction* — no write, SCM, or LLM port is ever injected into it.

```mermaid
flowchart LR
    gh["GitHub App<br/>(Sidsol/living-adr)"] -- "merged PR webhook" --> tunnel["Public HTTPS tunnel"]
    tunnel --> recv

    subgraph workflow["workflow-service (write path)"]
        direction TB
        recv["POST /webhooks/github<br/>verify + filter + persist"]
        evid["evidence fetch<br/>(GitHub App)"]
        clf["classify (schema/API + dependency)"]
        draft["ADR draft (Claude)"]
        hitl["HITL review UI<br/>(token-guarded)"]
        mint["mint one-shot capability"]
        write["approval-bound graph write"]
        pub["open ADR pull request"]
        recv -- "202, off-request" --> evid --> clf --> draft --> hitl
        hitl -- approve --> mint --> write --> pub
    end

    store[("SQLite WAL<br/>ingestion · checkpoints · audit")]
    graph[("property graph<br/>(approved ADRs)")]
    recv --> store
    write --> graph
    pub -. "PR back" .-> gh

    subgraph mcp["mcp-context-server (read path, read-only)"]
        q["list_adrs · fetch_adr · answer_why"]
    end
    graph --> q --> ide["IDEs / AI assistants (MCP)"]
```

The workflow graph itself is a durable, interruptible state machine:
`intake → classify → draft → HITL interrupt → (approve) → mint → mutate → publish`,
with `reject`/`defer` routing to terminal no-write states.

### 2.2 Key architecture decisions

The decisions below are presented in ADR form (Context / Decision / Rationale /
Alternatives / Consequences), which is fitting for a system about ADRs.

**AD-1 — Capture at PR-merge, event-driven.**
*Context:* rationale is freshest at the moment a change merges.
*Decision:* trigger drafting from the GitHub *merged pull-request* webhook.
*Rationale:* zero author effort; the diff + PR metadata are the richest available
evidence; capture happens even when no human would have written an ADR.
*Alternatives:* manual ADR authoring (the status-quo failure mode); periodic
repository scans (stale, lossy, no clear decision boundary).
*Consequences:* depends on webhook delivery + a public endpoint; only merged PRs
are considered.

**AD-2 — Human-in-the-loop approval, never autonomous.**
*Context:* LLMs draft well but cannot be trusted to *decide* or publish.
*Decision:* every draft pauses at a durable human-review gate; nothing becomes
authoritative or is published without an explicit human approval.
*Rationale:* trust, safety, and auditability; matches the "capable drafter,
untrustworthy decider" asymmetry.
*Consequences:* requires durable interrupt/resume and a review UI; throughput is
bounded by reviewer availability (acceptable and intended).

**AD-3 — LangGraph for durable, interruptible orchestration.**
*Context:* the workflow must pause for human review (potentially across process
restarts) and resume deterministically.
*Decision:* model the workflow as a LangGraph state graph with a SQLite
checkpointer; the HITL gate is a first-class `interrupt`.
*Rationale:* native interrupt/resume + durable checkpoints give restart-safe HITL
"for free"; deterministic thread identity (repository + normalized event key)
makes replays idempotent.
*Alternatives:* a hand-rolled state machine (re-implements checkpointing/resume);
a task queue such as Celery (no first-class human-interrupt semantics).
*Consequences:* adds the LangGraph dependency and a checkpoint store; node seams
must be msgpack-serializable.

**AD-4 — Approval-bound, one-shot capability for every authoritative write.**
*Context:* the core safety property is "no authoritative change without human
approval."
*Decision:* approving mints a one-shot `ApprovedReviewDecision` capability bound
to the exact reviewed content hash and the precise mutation target; the graph
write is the *only* code path allowed to mutate authoritative state, and it
validates + consumes the capability exactly once (with an append-only audit).
*Rationale:* makes the safety invariant structural rather than procedural; replay,
content drift, scope mismatch, and TTL expiry all fail closed.
*Consequences:* introduces a minting/validation/consumption layer; content
binding must be consistent across the draft, review, and write stages (see §3.4).

**AD-5 — Property graph + read-only MCP for context serving.**
*Context:* consumers need to ask "why is the architecture this way?" and trust the
answer.
*Decision:* store approved ADRs in a local property graph (LlamaIndex
`SimplePropertyGraphStore`) and expose them over a **read-only** MCP server
(`list_adrs`, `fetch_adr`, `answer_why`) with citations.
*Rationale:* graphs naturally express ADR↔evidence↔code-area relationships;
answers carry provenance; MCP is the emerging standard for grounding IDEs/agents.
*Alternatives:* a vector store (good for fuzzy recall, weaker for authoritative,
cited, relationship-aware answers); flat Markdown files (not programmatically
queryable with provenance).
*Consequences:* the read and write sides must agree on a shared graph root
(`${LIVING_ADR_STORAGE_PATH}/graph`).

**AD-6 — Ports-and-adapters (hexagonal) with fakeable seams.**
*Context:* the system integrates GitHub, an LLM, and a graph store; tests must
never touch the network.
*Decision:* depend on provider-neutral protocols (`SCMProvider`, `ClaudeClient`,
graph-store ports, `GitHubClient` transport) with injectable fakes.
*Rationale:* deterministic, offline, fast tests; providers (model, SCM) are
swappable; the live wiring is a thin composition layer.
*Consequences:* more interfaces; a small amount of composition glue per deployable.

**AD-7 — GitHub App authentication (not a personal token).**
*Decision:* authenticate as a GitHub App — sign a short-lived RS256 JWT from the
App private key, exchange it for a per-installation access token, and call the
REST API with that token.
*Rationale:* installation-scoped least privilege, no human-owned credential,
rotating tokens; the right model for an automated actor that writes back to repos.
*Consequences:* requires App registration, a private key kept out of git, and an
installation id in config.

**AD-8 — SQLite (WAL), single-writer, same-host.**
*Decision:* persist ingestion deliveries, workflow checkpoints, and the approval
audit in SQLite with WAL journaling; the workflow service is the sole writer.
*Rationale:* durable across restarts, dependency-free, and sufficient for a
single-repo PoC; WAL lets the single writer and read snapshots coexist on one
host.
*Consequences:* explicitly a same-host pattern (never a network filesystem); a
post-PoC scale-out would migrate the store.

**AD-9 — Anthropic Claude behind a provider-neutral seam.**
*Decision:* draft ADRs with Claude (`claude-sonnet-4-6` by default), accessed only
through the SDK-free `ClaudeClient` protocol.
*Rationale:* strong instruction-following and structured-output quality for
turning evidence into a well-formed ADR; the seam keeps the model swappable and
keeps the SDK out of the rest of the codebase. (Quantitative selection evidence is
deferred to Section 4.)

### 2.3 Framework and technology rationale (summary)

| Concern | Choice | Why |
|---|---|---|
| Language / runtime | Python `>=3.12,<3.13`, managed with `uv` | Rich AI/ML ecosystem; reproducible, fast dependency management |
| Webhook + review UI | FastAPI + uvicorn | Async HTTP, raw-body access for HMAC, server-rendered HITL UI |
| Orchestration | LangGraph (+ `langgraph-checkpoint-sqlite`) | Durable, interruptible HITL workflow with deterministic resume |
| LLM | Anthropic Claude (via `ClaudeClient` seam) | Structured ADR drafting; model swappable |
| Context store | LlamaIndex property graph | Relationship-aware, cited, authoritative context |
| Context serving | Model Context Protocol (stdio) | IDE/agent-native, read-only grounding |
| Auth | GitHub App (PyJWT + cryptography, httpx) | Scoped, rotating, least-privilege automation |
| Persistence | SQLite (WAL) | Durable, dependency-free, same-host single-writer |
| Validation | Pydantic v2 | Typed, frozen domain contracts |

### 2.4 Cross-cutting principles

- **Security boundary:** authoritative writes go only through the approval-bound
  path with a valid one-shot capability; the MCP read path has no write/SCM/LLM
  port.
- **Default-deny telemetry:** observability is metadata-only — never raw diffs,
  prompts, ADR bodies, citations, tokens, or secrets.
- **Secrets isolation:** secrets live only in the environment / `.env` / a
  gitignored `secrets/` directory — never in YAML config or version control.
- **Fail-fast startup:** invalid configuration or a missing webhook secret aborts
  the process before it can serve traffic.

---

## 3. Implementation Progress and Validation Evidence

### 3.1 Delivery approach

The system was built **incrementally and test-first**. Each capability was added
as a thin, independently testable slice behind a provider-neutral seam, with
fakes standing in for GitHub, Claude, and the graph store so the suite never
touches the network. Each phase was then **live-verified** against real GitHub and
real Claude before moving on.

### 3.2 Progress against the end-to-end loop

The full loop — from merged PR to published ADR to served context — is
**implemented and live-verified**.

| # | Capability | Status | Live evidence |
|---|---|---|---|
| 1 | Receive → verify → filter → persist | ✅ done + verified | HMAC-verified deliveries persisted; correct status codes |
| 2 | Evidence fetch (GitHub App) | ✅ done + verified | Real PR fetch: 10 changed files, 24,834 diff bytes |
| 3 | Classify → draft (Claude, off-request) | ✅ done + verified | Real ADR draft generated; classifier confidence 0.8 |
| 4 | Human review UI (token-guarded) | ✅ done + verified | Draft renders at `/hitl/reviews/{id}`; 401 without token, 200 with |
| 5 | Approve → graph write → publish PR | ✅ done + verified | One real PR opened on the tracked repo |
| 6 | Read-only MCP serves approved ADRs | ✅ done + verified | `answer_why`/`list_adrs` return the approved ADR with citations |
| 7 | Durable, scripted hosting | ✅ done | Receiver + persistent tunnel; helper run scripts |
| 8 | End-to-end validation + docs | ✅ done | This report; updated README/AGENTS |

### 3.3 Concrete validation evidence

The loop was exercised end to end against the live repository
`github.com/Sidsol/living-adr`:

- **Ingestion & evidence.** A merged-pull-request delivery was HMAC-verified,
  accepted (`202`), and its evidence fetched from GitHub via the App: the real PR
  metadata, **10 changed files** (e.g. `pyproject.toml`, `README.md`, source and
  test files), and the diff summarized as **24,834 diff bytes** (only a handle and
  summary are stored — never the raw diff).
- **Classification & drafting.** The composite classifier flagged the
  `pyproject.toml` dependency change as architecture-significant
  (**confidence 0.8**), and Claude generated a well-formed, PROVISIONAL ADR draft
  (*"Add New Python Dependency via pyproject.toml"*) with Context / Decision /
  Alternatives / Consequences / Citations. Drafting ran **off the webhook
  request** (background task), so the webhook returned promptly within GitHub's
  delivery timeout.
- **Human review.** The draft paused at a durable HITL checkpoint and rendered in
  the token-guarded review UI: requests **without** the UI token were rejected
  (`401`); requests **with** it returned the draft (`200`).
- **Approval-bound write.** Approving minted a one-shot capability and performed
  the approval-bound write of the ADR node into the local property graph; the
  workflow settled to `COMPLETED` (a no-write outcome would have resulted without
  a valid capability).
- **Publish-back.** A **real pull request** was opened on the repository carrying
  the approved ADR on a per-decision branch
  (`livingadr/adr-<decision-id>`) into the configured target branch.
- **Context serving.** Reading the shared graph root through the read-only adapter
  returned the approved ADR via `list_adrs` (status: *approved*) and produced a
  cited `answer_why` response referencing the ADR and its supporting evidence id.

### 3.4 Notable engineering findings

- **Cross-feature content-hash reconciliation.** Wiring the real drafting node to
  the real approval-bound write surfaced a latent inconsistency: the draft layer
  hashed *structured fields* while the approval layer validated the *rendered
  Markdown*. This was resolved at the root by binding the reviewed/approved content
  hash to the canonical hash of the exact rendered Markdown the reviewer sees and
  the write re-validates — making the "content changed since approval" guard hold
  for real drafts.
- **Respecting webhook timeouts.** Because LLM drafting is slow relative to a
  webhook's delivery timeout, the receiver accepts and persists synchronously and
  schedules drafting **off the request path** in a background worker, opening its
  own short-lived store connection to stay thread-safe.

### 3.5 Quality metrics

- **Automated tests:** **880 passing**, with provider-neutral fakes so the suite
  runs fully offline (no GitHub/Claude/network calls in tests).
- **Static analysis:** linter (ruff) clean across the codebase.
- **Methodology:** red/green TDD per slice; live smoke verification per phase.
- **Operational safety:** fail-fast startup on invalid config/secret; metadata-only
  telemetry; secrets isolated from config and version control.

### 3.6 Known limitations (current)

- **Single repository** (no multi-repo governance/discovery/fan-out).
- **No hot reload** — configuration and environment are read once at startup;
  restart to apply changes.
- **Hosting is scripted, not auto-supervised** — helper scripts plus a persistent
  tunnel; OS-level auto-restart (Scheduled Task / service) is documented but not
  configured.
- **Approve-after-edit** records the decision but does not yet re-inject the edited
  Markdown into the published record (plain approve publishes the reviewed draft).
- **Publication is gated by the completed approval** (which consumed the one-shot
  capability for the graph write) rather than a second independent capability.
- LangGraph emits benign msgpack "unregistered type" deprecation warnings on
  checkpoint reload.

---

## 4. Model Selection and Benchmark Evidence *(outline)*

> *To be completed in the next revision.* Intended contents:

- **Selection criteria:** structured-output fidelity (valid ADR sections),
  instruction-following, latency, cost per draft, context-window adequacy for
  diff+evidence, and safety/refusal behavior.
- **Current choice:** Anthropic Claude (`claude-sonnet-4-6`) accessed through the
  provider-neutral `ClaudeClient` seam (model is swappable without touching the
  workflow).
- **Benchmark plan:** a fixed set of representative merged-PR fixtures scored for
  (a) draft validity/parse rate, (b) faithfulness to the evidence (no fabricated
  citations), (c) reviewer edit distance, (d) latency and token cost. Candidate
  comparison across model families/sizes.
- **Evidence to gather:** parse-success rate, citation-grounding rate, reviewer
  acceptance rate, p50/p95 latency, cost per ADR.

## 5. RAG / Reasoning Pipeline Design *(outline)*

> *To be completed in the next revision.* Intended contents:

- **Reasoning pipeline (write path):** evidence assembly → structural
  classification → drafting-policy gate (external-LLM egress allowed?) → token
  budgeting → prompt assembly → Claude completion → strict ADR parsing → citation
  resolution. (Largely implemented; to be documented in depth with the prompt
  contract and budget policy.)
- **Retrieval (read path):** graph-grounded `answer_why` — traversal over the
  approved-ADR property graph returning cited answers; relationship to classical
  vector RAG and why a property graph was chosen for authoritative, cited recall.
- **Determinism & safety:** no raw diff/file contents enter classification;
  approved-context-only retrieval on the read side.

## 6. Responsible AI Analysis (Risks and Mitigations) *(outline)*

> *To be completed in the next revision.* Risk areas and current mitigations:

- **Hallucinated rationale / fabricated citations** → human approval gate;
  citation resolution; provenance on every served answer.
- **Unauthorized/automated change** → approval-bound one-shot capability; read-only
  MCP; append-only audit trail.
- **Data leakage via telemetry** → metadata-only, default-deny observability.
- **Prompt injection from PR content** → drafts are PROVISIONAL and human-approved;
  the read path performs no actions.
- **Secret exposure** → secrets isolated to env/`secrets/`; never logged or
  committed.
- **Bias / over-trust of drafts** → "PROVISIONAL — not authoritative until human
  approval" framing throughout; reviewer can edit/reject.

## 7. Lessons Learned and Future Work *(outline)*

> *To be completed in the next revision.* Themes:

- **Lessons:** value of provider-neutral seams for offline TDD; the importance of a
  single canonical content-hash convention across features; off-request execution
  to respect webhook SLAs; "capable drafter, untrustworthy decider" as a product
  axis.
- **Future work:** multi-repository support; production hosting with supervision
  and a stable public endpoint; richer graph relationships and `answer_why`
  retrieval; approve-after-edit publishing the edited body; a second
  publication-scoped capability; model benchmarking (Section 4); observability
  export.

---

## Appendix A — Glossary

- **ADR** — Architecture Decision Record: a short document capturing a decision,
  its context, alternatives, and consequences.
- **HITL** — Human-in-the-loop: the mandatory human approval gate.
- **MCP** — Model Context Protocol: the standard used to serve approved context to
  IDEs/agents (read-only here).
- **One-shot capability** — an `ApprovedReviewDecision` bound to a specific
  reviewed content and mutation target, valid for exactly one authoritative write.
- **Property graph** — the relationship-aware store of approved ADRs and their
  evidence.

## Appendix B — Technology summary

Python 3.12 (`uv`) · FastAPI + uvicorn · LangGraph (+ SQLite checkpointer) ·
Anthropic Claude (`claude-sonnet-4-6`, behind a provider-neutral seam) ·
LlamaIndex property graph · Model Context Protocol (stdio) · GitHub App auth
(PyJWT + cryptography + httpx) · SQLite (WAL) · Pydantic v2. Two deployables:
`living-adr-workflow` (HTTP write path) and `living-adr-mcp` (stdio read path).
880 automated tests; linter clean.
