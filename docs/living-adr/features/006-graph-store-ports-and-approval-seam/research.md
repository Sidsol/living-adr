# Codebase Research: LivingADR graph and approval seams

> **Vocabulary sidecar:** Not created for this greenfield feature because the requested deliverable set is limited to the eight feature-level planning artifacts. Codebase-observed vocabulary is captured inline with file references.

## Architecture Overview

`C:\repos\living-adr` is a very early Python 3.12 scaffold. The package currently exposes only a `main()` function that prints a greeting (`src\living_adr\__init__.py:1-2`) and a single import smoke test (`tests\test_import.py:1-5`). `pyproject.toml` already declares the expected LivingADR technology stack: FastAPI, LangGraph, LangSmith, LlamaIndex, MCP, Pydantic, PyYAML, pytest, pytest-asyncio, and Ruff (`pyproject.toml:10-35`).

Project planning documents define the intended architecture more fully. `architecture.md#service-boundaries` assigns domain types and ports to `core`, concrete graph implementation to `graph`, the workflow writer to `workflow-service`, and read-only context delivery to `mcp-context-server`. `architecture.md#data-model` names `ADRRecord`, `ArchitectureGraph`, `ApprovedReviewDecision`, and repository-scoped records. `architecture.md#cross-cutting` states the approval-bound capability flow and source-of-truth hierarchy.

## Directory Structure

Observed implementation structure:

```text
living-adr\
├── README.md                         # Getting-started note; uv sync and uv run pytest
├── pyproject.toml                    # Python 3.12 package metadata and dependencies
├── living-adr.config.example.yaml    # Example tracked-repository configuration
├── src\living_adr\__init__.py        # main() smoke entrypoint only
└── tests\test_import.py              # import smoke test only
```

No `core`, `graph`, `workflow_service`, `mcp_context_server`, adapter, approval, or conformance modules exist yet.

## Logic Flows

### Flow: Package import smoke

1. Test imports `main` from `living_adr` (`tests\test_import.py:1`).
2. Test asserts the imported object is callable (`tests\test_import.py:4-5`).
3. `main()` prints `Hello from living-adr!` (`src\living_adr\__init__.py:1-2`).

### Flow: Intended approved graph mutation boundary

1. HITL UI mints an `ApprovedReviewDecision` after explicit approval (`architecture.md#service-boundaries`).
2. Workflow requests mutation through `ApprovalBoundMutationService`, not directly through the graph adapter (`architecture.md#service-boundaries`).
3. Service validates approval capability, repository match, and draft content hash before write (`architecture.md#service-boundaries`).
4. Only after validation does it call `ArchitectureGraphStore` (`architecture.md#service-boundaries`).
5. Mutation and audit records link by `decision_id` (`architecture.md#cross-cutting`).

This flow is not implemented in code yet.

### Flow: Intended read-only context query

1. MCP context server receives an IDE/assistant request (`architecture.md#service-boundaries`).
2. MCP uses only `ArchitectureContextQuery`, not mutation services or SCM credentials (`architecture.md#service-boundaries`).
3. Query methods filter by `RepositoryIdentity` and return ADR citations/provenance (`architecture.md#data-model`).

This flow is not implemented in code yet.

## Data Models

### Model: Repository configuration example

- Location: `living-adr.config.example.yaml:1-18`
- Fields observed: `repository_identity.provider`, `owner`, `name`; `github_app.installation_id`; `adr_publication.policy`, `branch`, `path`; `llm.external_llm_allowed`.
- Observation: This example uses `draft_only`, `pull_request`, and `direct_commit` comments (`living-adr.config.example.yaml:11-15`), while feature 002 intent and architecture use `livingadr_only`, `publish_to_github`, and `publish_to_github_and_livingadr`. Implementation should reconcile with the architecture/feature 002 contract rather than the stale scaffold comment.

### Model: ApprovedReviewDecision

- Location: planned in `architecture.md#data-model` and `architecture.md#service-boundaries`.
- Fields: `decision_id`, `reviewer_id`, minted time, TTL, consumed marker, draft id, draft content hash, structural change event id, decision version, and target mutation fingerprint.
- Relationships: authorizes exactly one approved graph mutation target; links review event, graph mutation, and audit event.

### Model: ADRRecord

- Location: planned in `architecture.md#data-model`.
- Fields: repository scope, human-readable Markdown content, structured metadata/projection, status, citations/provenance, approved decision linkage.
- Relationships: authoritative rationale source; graph node is a projection of this record.

### Model: ArchitectureGraph

- Location: planned in `architecture.md#data-model` and `architecture.md#service-boundaries`.
- Fields/relationships: ADRs, components, dependencies, schemas, API contracts, PRs, commits, supersession links, evidence citations, repository scope, schema version.
- Relationships: queryable projection with citations back to approved ADR/evidence.

## Integration Points

| Integration | Type | Location | Notes |
|---|---|---|---|
| LlamaIndex Property Graph | Graph adapter | `pyproject.toml:16-17`; planned `architecture.md#service-boundaries` | Dependency exists, adapter not implemented. Ports must not expose LlamaIndex types. |
| LangGraph | Workflow orchestration | `pyproject.toml:14`; planned `architecture.md#tech-stack` | Future workflow consumes approval-bound mutation seam. |
| MCP SDK | Context delivery | `pyproject.toml:18`; planned `architecture.md#service-boundaries` | Future MCP server consumes read-only query port. |
| LangSmith | Observability | `pyproject.toml:15`; feature 002 intent | Core ports should use `Observability` abstraction and avoid direct LangSmith imports. |
| GitHub App / SCM | Evidence and publication | planning docs | Not implemented in code; all relevant records must retain `RepositoryIdentity`. |

## Configuration & Environment

- `README.md:5-7` states `uv sync` and `uv run pytest` as setup/test commands.
- `pyproject.toml:31-35` defines dev dependencies for pytest and Ruff.
- `living-adr.config.example.yaml` exists but may predate feature 002's intended config shape.
- Feature 002 intent defines `RepositoryIdentity`, `RepositoryConfig`, `LivingADRConfig`, and a thin `Observability` port as dependency contracts.

## Technical Debt & Observations

- The repository is scaffold-only; all graph, approval, ADR, and context modules are absent.
- Config example terminology appears inconsistent with architecture and feature 002 intent, so feature 006 should reference feature 002 contracts and avoid introducing a second config vocabulary.
- `pyproject.toml` already includes concrete infrastructure dependencies; core port modules must avoid importing them to keep the seam swappable.
- Existing tests are smoke-level only; conformance and contract tests will be newly introduced by this feature.

## Key Patterns

- Planned architecture favors a single repo with two deployables and shared `core` contracts.
- Ports live in `core`; implementations live behind adapters.
- Every domain record and operation is repository-scoped.
- Human-approved ADR records are authoritative; graph data is a projection.
- Graph mutation is intended to be centralized behind `ApprovalBoundMutationService`.
