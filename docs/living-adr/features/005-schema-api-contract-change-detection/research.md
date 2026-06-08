# Codebase Research: living-adr

> **Vocabulary sidecar:** Not produced for this planning-only run; codebase-discovered vocabulary is captured inline because the current implementation is scaffold-only.
>
> **Blindness note:** The project is greenfield and only scaffold code exists. Research was based on current repository structure and project planning artifacts, not on an existing schema/API classifier implementation.

## Architecture Overview

`C:\repos\living-adr` is a Python 3.12 scaffold with `uv`, pytest, Ruff, FastAPI, LangGraph, LlamaIndex, Anthropic, MCP, and Jinja dependencies declared in `pyproject.toml`. The source tree currently contains only `src\living_adr\__init__.py`, and the test tree contains only `tests\test_import.py`. There are no production modules yet for `core`, `scm`, `workflow`, `graph`, `hitl`, classifier logic, persistence, observability, or app entry points.

Project architecture documents define the intended shape: a single repository with two deployables (`workflow-service` and `mcp-context-server`) and shared internal packages under `src\living_adr\core`, `scm`, `workflow`, `graph`, `hitl`, and `observability` (`..\..\architecture.md#service-boundaries`).

## Directory Structure

| Path | Current purpose | Observations |
|---|---|---|
| `C:\repos\living-adr\pyproject.toml` | Python package and dependency declaration | Declares Python `>=3.12,<3.13`, runtime dependencies, dev dependencies, and one script `living-adr = living_adr:main`. |
| `C:\repos\living-adr\src\living_adr\__init__.py` | Package entry point | Contains only `main()` that prints a scaffold greeting. |
| `C:\repos\living-adr\tests\test_import.py` | Smoke test | Imports `main` and asserts it is callable. |
| `C:\repos\living-adr\.github\workflows\ci.yml` | CI workflow | Present; details should be checked during implementation before changing test/lint assumptions. |
| `C:\repos\living-adr\docs\adr\.gitkeep` | ADR directory placeholder | No ADR records exist yet. |
| `C:\repos\living-adr\living-adr.config.example.yaml` | Example config | Present from earlier scaffold/config planning; must remain separate from secrets. |

## Logic Flows

### Flow: Package import smoke

1. Entry point: `src\living_adr\__init__.py` defines `main()`.
2. Test: `tests\test_import.py` imports `main`.
3. Assertion: smoke test confirms `main` is callable.

No workflow-service, SCM event, evidence, classifier, graph, or MCP flow exists in code yet.

### Flow: Intended merged-PR evidence pipeline (planned, not implemented)

1. GitHub webhook delivery enters `workflow-service` per `..\..\architecture.md#service-boundaries`.
2. Feature 003 normalizes accepted merged PRs into `SCMEvent` and candidate evidence.
3. TH-02 classifiers consume the evidence and emit `StructuralChange` / `ChangeEvidence` per `..\..\architecture.md#data-model`.
4. Feature 008 drafts ADRs from structural changes, feature 009/010 review and approve, and graph features persist approved rationale.

This flow is architectural intent only; there is no current code path.

## Data Models

### Existing code models

No domain models are implemented in the current source tree.

### Planned architecture-level models relevant to this feature

| Model | Source | Notes |
|---|---|---|
| `RepositoryIdentity` | `..\..\architecture.md#data-model` | Stable repository scope required on every domain record. |
| `SCMEvent` | `..\..\architecture.md#data-model`; feature 003 intent | Normalized merged-PR event envelope with provider delivery identity and fetch handles. |
| `ChangeEvidence` | `..\..\architecture.md#data-model` | Immutable evidence from PR metadata, diff summaries, schema/API signals, linked text, and retrieval context. |
| `StructuralChange` | `..\..\architecture.md#data-model` | Classified architecture-significant change such as dependency, schema, or API-contract change. |
| `ADRDraft` | `..\..\architecture.md#data-model` | Provisional downstream artifact, not authoritative before HITL. |

## Integration Points

| Integration | Type | Current location | Notes |
|---|---|---|---|
| GitHub App webhooks | External HTTP/SCM | Planned `workflow-service` / `scm` | Feature 003 owns HMAC, filtering, `SCMEvent`, evidence fetches, replay/dead-letter. |
| Claude via Anthropic | External LLM | Planned adapter | Not used by this feature; downstream feature 008 uses structural changes. |
| LangGraph | Workflow runtime | Planned `workflow` | Feature 015 invokes classifier nodes after ingestion. |
| LlamaIndex property graph | Graph adapter | Planned `graph` | Not used by classifiers directly; graph mutation occurs after HITL. |
| Observability | Metadata traces | Planned `core\observability.py` / feature 013 adapter | This feature should emit metadata only, not raw diffs. |

## Configuration & Environment

`pyproject.toml` already includes the expected runtime packages. Feature-level implementation should not add new dependencies unless a detector requires a lightweight parser that cannot be reasonably implemented from available evidence. Repository configuration and external LLM policy are owned by feature 002; classifier thresholds should be represented as a typed configuration or policy object that can later move into repository config if needed.

## Technical Debt & Observations

- The codebase is scaffold-only; any classifier implementation will create new package structure rather than modify existing behavior.
- `pyproject.toml` currently has a generic package description and one placeholder console script; feature implementation should not rely on production app entry points being present.
- There is no existing `StructuralChange` type in code. Feature 005 must coordinate with feature 004/006 style contracts and avoid defining schema/API-specific common fields that would block dependency changes.
- There is no existing persistence or evidence store. The classifier should be pure over feature 003 evidence records and leave persistence to ingestion/workflow features.
- There is no existing threshold configuration. The confidence threshold is an explicit open decision and should be encoded as policy, not magic numbers buried in detectors.

## Key Patterns

- Planning artifacts use repository-scoped domain contracts and provider-neutral seams.
- The architecture favors typed ports in `core`, concrete adapters outside `core`, and deterministic tests with fakes before live integrations.
- Raw repository/diff content is treated as untrusted input and default-deny for observability export.
- Human approval is required before authoritative ADR or graph mutation; classifier output is evidence/provisional signal only.
