# Codebase Research: LivingADR dependency-change-detection

> **Blindness note:** LivingADR is greenfield; no production repository exists in this planning folder. Research is therefore a read-only synthesis of project-level architecture and dependency feature contracts, with no dependency on production code. The feature goal was not used to inspect source code because there is no source tree yet.

## Architecture Overview

LivingADR is planned as one Python 3.12 repository, `living-adr`, with two deployables: `workflow-service` and `mcp-context-server`. The workflow service owns GitHub webhook ingestion, SCM normalization, LangGraph orchestration, Claude calls, HITL review, audit state, and approved graph mutation. The MCP context server is read-only and depends on query ports only (`..\..\architecture.md#service-boundaries`).

Shared `core` owns domain types and ports, including `RepositoryIdentity`, `SCMProvider`, `StructuralChange`, `ChangeEvidence`, graph ports, audit, and observability. SCM-specific code lives under `scm`; workflow orchestration under `workflow`; graph adapters under `graph` (`..\..\architecture.md#service-boundaries`).

## Directory Structure

Planned repository layout from `..\..\architecture.md#tech-stack`:

```text
C:\repos\living-adr\
  pyproject.toml
  uv.lock
  src\living_adr\
    apps\workflow_service\
    apps\mcp_context_server\
    core\
    scm\
    graph\
    workflow\
    hitl\
    observability\
  tests\
  var\.gitkeep
```

Relevant planned areas:

| Area | Observed responsibility |
|---|---|
| `src\living_adr\core` | Domain records and ports, including repository scope, SCM events, structural changes, evidence, graph ports, and observability. |
| `src\living_adr\scm` | GitHub provider and future Azure DevOps provider; owns provider-specific payload/API details. |
| `src\living_adr\workflow` | LangGraph workflow nodes, evidence handoff, replayable workflow state, and classifier orchestration. |
| `src\living_adr\apps\workflow_service` | FastAPI process for webhook/HITL service boundaries. |
| `tests` | Pytest suite planned for unit/integration verification. |

## Logic Flows

### Flow: Merged PR evidence intake

1. GitHub sends a merged PR webhook to `workflow-service` (`..\..\architecture.md#service-boundaries`).
2. Feature 003 verifies HMAC, filters configured merged PRs, and normalizes into `SCMEvent` with repository identity, provider delivery id, normalized PR key, timestamps, and fetch handles.
3. Feature 003 fetches minimal PR metadata, changed file metadata, and diff handles/summaries through `SCMProvider`/`GitHubProvider`.
4. Feature 003 emits immutable candidate evidence linked to `SCMEvent`, provider delivery id, normalized PR key, and provenance (`..\003-github-webhook-ingestion\spec.md`).
5. Downstream structural-change classifiers consume candidate evidence, not raw GitHub payloads.

### Flow: Structural classification to ADR drafting

1. A classifier emits repository-scoped `StructuralChange` records for architecture-significant changes (`..\..\architecture.md#data-model`).
2. `ChangeEvidence` remains separate from inferred rationale and records source PR/diff facts (`..\..\architecture.md#data-model`).
3. Feature 008 receives approved structural-change candidates plus relevant graph context and generates provisional `ADRDraft` records (`..\..\feature-map.md`, feature 008 brief).
4. HITL approval is required before graph mutation (`..\..\architecture.md#service-boundaries`, `..\..\architecture.md#cross-cutting`).

### Flow: No-ADR-needed suppression

1. Domain anti-pattern FM-03 warns against ADR fatigue, and architecture constrains PoC triggers to new dependencies, schema changes, and API-contract changes (`..\..\architecture.md#anti-patterns`).
2. Classifiers must distinguish meaningful structural changes from low-signal changes.
3. Below-threshold outcomes should be explicit and replayable so downstream drafting does not run accidentally.

## Data Models

### Model: `RepositoryIdentity`

- Location: Architecture data model (`..\..\architecture.md#data-model`).
- Fields: stable `host/owner/repo` key plus opaque provider `repo_id`.
- Relationships: scopes every domain record, SCM call, graph node, and MCP query.

### Model: `SCMEvent`

- Location: Architecture data model and Feature 003 contracts.
- Fields: repository, provider delivery identity, normalized event key/PR key, timestamps, PR refs, merge commit SHA, fetch handles.
- Relationships: source envelope for candidate evidence and downstream structural-change classification.

### Model: `ChangeEvidence`

- Location: Architecture data model.
- Fields: repository; immutable evidence from merged PR metadata, diff summaries, dependency/schema/API-contract signals, linked text, retrieval context.
- Relationships: stored separately from inferred rationale; referenced by `StructuralChange`, later drafts, and citations.

### Model: `StructuralChange`

- Location: Architecture data model and graph-port type sketch.
- Fields: repository; classified architecture-significant change such as dependency, schema, or API-contract change; links to source PR evidence and later approved ADR node.
- Relationships: Feature 004 is the first producer; Feature 005 adds additional producers; Feature 008 consumes it for drafting.

### Model: `ADRDraft`

- Location: Architecture data model.
- Fields: repository, provisional ADR draft and classification output.
- Relationships: never authoritative until HITL approval.

## Integration Points

| Integration | Type | Location | Notes |
|---|---|---|---|
| Feature 003 evidence stream | Internal port/model | `..\003-github-webhook-ingestion\spec.md`, `intent.md` | Produces `SCMEvent`, changed file metadata, diff handles/summaries, and immutable candidate evidence. |
| `Observability` | Internal port | `..\..\architecture.md#cross-cutting` | Metadata-only logs/traces; raw diffs and prompt bodies default-deny. |
| Feature 008 drafting | Downstream workflow consumer | `..\..\feature-map.md` feature 008 | Consumes dependency `StructuralChange` and evidence references to package Claude ADR prompts. |
| Feature 015 orchestration | Downstream workflow integration | `..\..\roadmap.md` M3 | Will invoke classifier nodes inside durable LangGraph workflow. |
| Graph store ports | Downstream approved mutation | `..\..\architecture.md#service-boundaries` | Only approved decisions can write structural changes into graph via `ArchitectureGraphStore`. |

## Configuration & Environment

- Python 3.12, uv, pytest, Ruff, FastAPI, LangGraph, LlamaIndex, Anthropic, SQLite are selected in architecture.
- `RepositoryConfig` is loaded from `living-adr.config.yaml` and every method must accept `RepositoryIdentity` scope.
- No classifier-specific live secrets should be needed. Thresholds should be config-driven or central constants with tests.
- Observability must omit raw diffs, full prompts, full pre-approval drafts, and reviewer comments by default.

## Technical Debt & Observations

- No production source tree exists yet, so file paths in implementation plans are planned paths, not observed code paths.
- The architecture leaves the exact confidence threshold open (`..\..\architecture.md#open-architectural-questions`), so Feature 004 must choose a tested default and keep it configurable.
- Feature 003 defines candidate evidence but exact implementation field names may evolve; Feature 004 should depend on typed core models rather than raw dictionaries.
- Feature 008 depends on this feature as the first `StructuralChange` producer, so contract stability matters more than broad package-manager coverage.

## Key Patterns

- Provider-specific SCM data stays inside adapters; workflow-facing types are provider-neutral.
- Code and PR data are evidence, not authoritative rationale.
- Structural evidence must be deterministic and replayable.
- Graph mutation is impossible without HITL-approved `ApprovedReviewDecision`.
- PoC favors SQLite/WAL, local fixtures, and deterministic tests over external infrastructure.
