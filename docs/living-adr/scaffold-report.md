# Scaffold Report — LivingADR

**Date:** 2026-05-25

## Repos Initialized

| Repo | Status | Stack | Initial commit | Notes |
|------|--------|-------|----------------|-------|
| living-adr | initialized | Python 3.12 / uv | d7438f4f9031a0322a79b3e3a19039a3f4ded734 | Created at `C:\repos\living-adr` with `uv init --python 3.12 --package`; all requested dependencies added; `uv sync`, `uv run pytest`, and `uv run ruff check .` passed. |

## Stack & Dependencies

No dependency substitutions were needed.

| Dependency | Command | Result | Notes |
|------------|---------|--------|-------|
| langgraph | `uv add langgraph` | succeeded | Added baseline orchestration dependency. |
| llama-index | `uv add llama-index` | succeeded | Added baseline graph/retrieval dependency. |
| llama-index-core | `uv add llama-index-core` | succeeded | Added direct core dependency. |
| anthropic | `uv add anthropic` | succeeded | Added Claude SDK dependency. |
| mcp | `uv add mcp` | succeeded | Canonical official Python MCP SDK package name; no substitution. |
| fastapi | `uv add fastapi` | succeeded | Added HITL/webhook HTTP framework dependency. |
| jinja2 | `uv add jinja2` | succeeded | Added server-rendered HTML template dependency. |
| uvicorn | `uv add uvicorn` | succeeded | Added ASGI server dependency. |
| langsmith | `uv add langsmith` | succeeded | Added observability/tracing dependency. |
| pydantic | `uv add pydantic` | succeeded | Added validation/modeling dependency. |
| pyyaml | `uv add pyyaml` | succeeded | Added YAML config dependency. |
| pytest | `uv add --dev pytest` | succeeded | Added test framework as a dev dependency. |
| pytest-asyncio | `uv add --dev pytest-asyncio` | succeeded | Added async pytest support as a dev dependency. |
| ruff | `uv add --dev ruff` | succeeded | Added lint/format tooling as a dev dependency. |

## Baseline Files Created

- `.gitignore` — merged Python, uv, environment, SQLite, coverage, and runtime config ignores.
- `README.md` — replaced uv placeholder with the §4 repository purpose and a short Getting Started stub.
- `.github/workflows/ci.yml` — minimal GitHub Actions CI for Python 3.12, uv sync, pytest, and Ruff.
- `living-adr.config.example.yaml` — commented deployment config stub for repository identity, GitHub App installation id, ADR publication policy, publish target, and external LLM policy.
- `docs/adr/.gitkeep` — preserves the future ADR publication directory.
- `tests/test_import.py` — non-runtime smoke test so `uv run pytest` and CI pass before feature work adds real tests.

## Remote Creation Commands (Copy-Paste)

> CRISPY does not create remote repos. Run this command yourself when ready. The repo may be private or public; private is recommended for an internal-tool PoC.

```bash
gh repo create <TO-BE-FILLED-BY-USER>/living-adr --private --source=C:\repos\living-adr --push --description "LivingADR — automated ADR archivist for the configured GitHub repository"
```

## Skipped / Failed

| Repo | Reason |
|------|--------|
| _None_ | _None_ |

## Next Steps

1. Run the `gh repo create` command above when ready.
2. Copy `living-adr.config.example.yaml` to `living-adr.config.yaml` and edit it for the deployment.
3. Proceed to feature-level CRISPY runs once Phase 4-6 complete.
