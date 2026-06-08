# Architecture Intent: approval-capability-and-audit-durability

## Current State

LivingADR architecture already defines the approval-bound mutation concept but the durable enforcement feature has not been planned. Feature 009 captures reviewer choices through a server-rendered UI and `ReviewResumeCommand`. Feature 015 checkpoints in-flight workflow state and routes approved states to mutation handoff. Feature 007 implements graph ports but leaves approval durability to this feature.

Relevant architecture anchors:

- `..\..\architecture.md#service-boundaries`: `ApprovalBoundMutationService` is the only write path to `ArchitectureGraphStore`; MCP is read-only.
- `..\..\architecture.md#data-model`: `ApprovalEvent` and `ApprovedReviewDecision` include repository scope, decision id, reviewer, content hash, structural change id, decision version, TTL, and consumption state.
- `..\..\architecture.md#tech-stack`: Python 3.12, FastAPI workflow-service, SQLite state/audit, pytest/Ruff.
- `..\..\architecture.md#cross-cutting`: fail-closed approval-bound mutation, transactional graph mutations, append audit events, default-deny raw observability.
- `..\..\architecture.md#anti-patterns`: avoid excessive agency, rubber stamping, hallucinated rationale becoming authoritative, and docs-as-code without review gates.
- `..\..\architecture.md#deployment`: PoC same-host single-writer SQLite/WAL; workflow-service is the writer.
- `..\..\architecture.md#repositories`: single `living-adr` repository.

## Desired State

Feature 010 provides durable approval authority. The workflow-service records all review outcomes, mints short-lived one-shot `ApprovedReviewDecision` capabilities for approved outcomes only, validates TTL/repository/hash/target fingerprint before mutation, records consumption atomically, and exposes `ApprovalBoundMutationService` as the only authoritative mutation entrypoint for graph writes and downstream publish-back coordination.

Audit durability is independent of feature 015 checkpointer durability. Checkpoints may pause/resume workflow; audit records prove approval and consumption.

## Options Considered

### Option A — Treat feature 009 approve as a boolean flag

**Approach:** Store `approved=True` in workflow state and let downstream graph/publish nodes mutate if that flag is present.

- Pros: Minimal code and easy workflow routing.
- Cons: No TTL, no content hash binding, no one-shot semantics, no durable audit separate from checkpoint, weak SM-05 evidence, and easy replay duplication.
- Decision: Rejected.

### Option B — Put approval state inside LangGraph checkpointer tables

**Approach:** Extend feature 015 checkpointed state with approval events and consumption metadata.

- Pros: Reuses existing durable storage and thread identity.
- Cons: Conflates orchestration state with audit facts; checkpoint compaction/replay/migration could damage audit history; violates feature 015 out-of-scope boundary.
- Decision: Rejected.

### Option C — Let the graph adapter enforce approval consumption

**Approach:** Pass approvals to `LlamaIndexPropertyGraphAdapter` and let it validate/consume decisions internally.

- Pros: Keeps validation close to graph writes.
- Cons: Couples audit semantics to the default adapter, weakens graph swappability, duplicates behavior for publish-back, and conflicts with feature 007's stated boundary.
- Decision: Rejected.

### Option D — Domain-level ApprovalBoundMutationService with separate audit repository (selected)

**Approach:** Implement approval event persistence, capability minting, validation, content hashing, consumption, idempotency, and audit linkage in domain/workflow-service code. Keep graph adapters behind ports and require all authoritative mutation/publish operations to pass through this service boundary.

- Pros: Matches architecture, preserves swappable graph ports, supports feature 011, separates audit from checkpointing, and gives strong SM-05 evidence.
- Cons: More service/repository code and transaction coordination.
- Decision: Selected.

## Selected Approach

Proceed with Option D. Implement a domain-level approval package and persistence layer in `living-adr` that is owned by workflow-service. The package consumes feature 015 review resume commands after feature 009 validation, records immutable audit events, mints `ApprovedReviewDecision`, validates capability state just-in-time, and delegates writes only through `ApprovalBoundMutationService`.

## Module Surface Analysis

| Module / Path | Purpose | Test Focus |
|---|---|---|
| `src\living_adr\approval\models.py` | `ApprovalEvent`, `ApprovedReviewDecision`, consumption/result DTOs, validation errors | Pure model and serialization tests |
| `src\living_adr\approval\hashing.py` | Canonical rendered ADR hash helper | Cross-platform SHA-256 tests |
| `src\living_adr\approval\repository.py` | Durable approval/audit repository protocol and SQLite implementation | Append-only, unique decision id, restart persistence |
| `src\living_adr\approval\minting.py` | Converts approved review resume commands into capabilities | Approve/edit/reject/defer behavior |
| `src\living_adr\approval\validation.py` | TTL, repository, content hash, target fingerprint checks | Error-path tests |
| `src\living_adr\approval\mutation_service.py` | `ApprovalBoundMutationService` orchestration and graph-store delegation | No direct writes, one-shot, idempotent retry |
| `src\living_adr\approval\audit_queries.py` | SM-05 and decision/mutation audit views | Query contract tests |
| `src\living_adr\workflow\approval_node.py` | Feature 015 seam adapter that attaches/mints approved decisions | Workflow integration tests |
| `tests\approval\...` | Unit/integration tests for approval durability and boundaries | End-to-end approval scenarios |

## Anti-Patterns to Avoid

- Treating feature 009 UI approval as authoritative without minting a capability.
- Storing audit facts only in feature 015 checkpoints.
- Letting `ArchitectureGraphStore` or feature 007 consume decisions directly without the approval service.
- Allowing feature 011 to publish with only `decision_id` text and no validated capability/fingerprint.
- Re-hashing non-canonical or platform-dependent content.
- Logging raw ADR drafts, reviewer comments, prompts, diffs, or private evidence.
- Allowing MCP or read-side query code to import mutation services.

## Affected Repositories

| Repository | Impact | Confidence |
|---|---|---|
| `living-adr` | Add approval domain package, SQLite audit tables/repository, workflow approval node seam, mutation service, audit query helpers, and tests. | High |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Duplicate mutation during replay | Medium | High | Atomic consumption table keyed by `decision_id` and target fingerprint; idempotent same-fingerprint result cache. |
| Audit/checkpoint conflation | Medium | High | Separate tables, repositories, and tests proving audit survives checkpoint reset simulation. |
| Content hash mismatch due line endings | Medium | Medium | Canonical LF/UTF-8 hashing helper used by 009/010 and tested with CRLF input. |
| Feature 011 bypasses approval | Medium | High | Publish contract documented in manifest and boundary tests requiring capability/decision linkage. |
| Transaction coordination with graph store fails | Medium | High | Validate and reserve consumption before mutation, finalize only with mutation result, record compensating failure event if adapter fails. |
| TTL too short for slow mutation | Low | Medium | Validate TTL at mutation start, not after successful graph write; default remains 10 minutes. |

## Decision

Use a domain-level approval and audit boundary with `ApprovalBoundMutationService` as the sole authoritative mutation path. Keep it independent from feature 015 checkpointer durability and adapter-neutral across feature 007 and future graph backends.
