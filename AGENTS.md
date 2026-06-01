# AGENTS.md

Guidance for AI coding agents working in (or alongside) the **living-adr** repo.

## What this project is

LivingADR auto-drafts **Architecture Decision Records (ADRs)** from merged GitHub
PRs, routes them through human approval, stores them in a property graph, and can
publish approved ADRs back into the source repository. It ships two deployables:

- `living-adr-workflow` — ingestion + ADR drafting + approval + publish-back.
- `living-adr-mcp` — a **read-only** Model Context Protocol (MCP) server that
  exposes approved architecture-decision context to IDEs and AI assistants.

## Using the LivingADR MCP server

The `living-adr-mcp` server lets an agent answer "why is the architecture this
way?" questions grounded in **approved** ADRs, with citations. It is **read-only
by construction**: it cannot mutate the graph, approve/publish ADRs, call
SCM/LLM providers, or change configuration.

### Available tools (all read-only)

| Tool | Use it to… | Key args |
|---|---|---|
| `list_adrs` | List approved ADRs for a tracked repo | `repository` (canonical key), optional `status` |
| `fetch_adr` | Read one approved ADR with its citations/provenance | `repository`, `adr_id`, optional `snapshot` |
| `answer_why` | Ask an architecture-rationale question and get a cited answer | `repository`, `question`, optional `code_area`, `limit` (default 5, max 10) |

The `repository` argument is the canonical key `host/owner/repo` — for this
project that is `github.com/Sidsol/living-adr`.

### When an agent should use it

- Before changing architecture-significant code, call `answer_why` /
  `list_adrs` to check whether an existing ADR already constrains the decision.
- When reviewing a PR, use `fetch_adr` to cite the governing decision.
- Treat results as **authoritative architectural context**, not suggestions —
  every answer carries citations/provenance back to an approved ADR.

### What it will NOT do

There are no `approve`, `edit`, `reject`, `publish`, `upsert`, `migrate`,
`rebuild`, `supersede`, or SCM-fetch tools. Approval and publication happen only
through the human-in-the-loop workflow service, never through the MCP server.

### Connection details

The server speaks **stdio** only (no HTTP in the PoC). It is registered for the
GitHub Copilot CLI in `~/.copilot/mcp-config.json` as `living-adr`:

```json
{
  "mcpServers": {
    "living-adr": {
      "command": "C:\\repos\\living-adr\\.venv\\Scripts\\living-adr-mcp.exe",
      "env": { "LIVING_ADR_CONFIG": "C:\\repos\\living-adr\\living-adr.config.yaml" }
    }
  }
}
```

For other MCP hosts (Claude Desktop, VS Code, etc.) use the same `command` +
`env`. The `env` block carries **only** the config path — never secrets. The
read-only server needs no write credentials.

See `docs/mcp-context-server.md` for the full tool contract and safety notes.

## Working in this repo

- **Runtime:** Python 3.12, managed with [uv]. Run `uv sync` to install.
- **Tests:** `uv run pytest` (must stay green — 828 tests at last sweep).
- **Lint:** `uv run ruff check .` (must stay clean).
- **Config:** `living-adr.config.yaml` (no secrets) + `.env` (secrets). Both are
  read once at **startup** — there is no hot reload, so restart both deployables
  after any change.
- **Onboarding check:** `uv run living-adr onboard validate --config living-adr.config.yaml`

## Safety invariants (do not break)

- Every authoritative graph/repo write goes through the approval-bound mutation
  path with a valid one-shot `ApprovedReviewDecision`. Never bypass it.
- Observability/telemetry is metadata-only (default-deny): never log raw diffs,
  prompts, ADR bodies, citations, tokens, or secrets.
- The MCP server stays read-only — never inject a write/SCM/LLM port into it.

[uv]: https://docs.astral.sh/uv/
