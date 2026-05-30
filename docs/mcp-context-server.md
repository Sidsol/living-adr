# living-adr-mcp — read-only MCP context server

`living-adr-mcp` is a **read-only** [Model Context Protocol](https://modelcontextprotocol.io)
server that exposes approved LivingADR architecture decision context to IDEs and
AI coding assistants. It is a thin adapter over the feature 007
`ArchitectureContextQuery` read port and **cannot** mutate the graph, approve or
publish ADRs, call SCM/LLM providers, or change configuration.

The PoC transport is **stdio only**. HTTP / Streamable HTTP, OAuth, and remote
hosting are deferred to a later feature.

## Exposed tools (all read-only)

| Tool | Purpose |
|---|---|
| `list_adrs` | List approved ADRs for a configured repository, with an optional status filter. Returns `ADRRef` data (id, title, status). |
| `fetch_adr` | Fetch one approved ADR with its citations/provenance. Accepts an optional `snapshot` id. |
| `answer_why` | Answer an architecture rationale ("why") question using approved ADR context, with citations. Bounded question length; `limit` defaults to 5 and clamps to 10. |

There are **no** `approve`, `edit`, `reject`, `publish`, `upsert`, `migrate`,
`rebuild`, `supersede`, `retract`, or SCM-fetch tools. The server is read-only by
construction: it is injected only with `ArchitectureContextQuery`,
`LivingADRConfig`, and the `Observability` port.

## Configuration

The server loads and validates `living-adr.config.yaml` through the feature 002
config contracts at startup and **fails fast** on invalid configuration. Point it
at your config with the `LIVING_ADR_CONFIG` environment variable, or run it from a
directory that contains `living-adr.config.yaml`.

The configuration file contains **no secrets** — repository onboarding records
only. Do **not** place SCM tokens, app private keys, or other credentials in the
MCP host configuration or in `living-adr.config.yaml`. The read-only MCP server
never needs write credentials; keep any secrets in your environment/vault for the
workflow service, not the MCP host.

## Local MCP host configuration (stdio)

Configure your MCP host (IDE / assistant) to launch the server over stdio. A
typical entry looks like:

```json
{
  "mcpServers": {
    "living-adr": {
      "command": "living-adr-mcp",
      "env": {
        "LIVING_ADR_CONFIG": "C:\\path\\to\\living-adr.config.yaml"
      }
    }
  }
}
```

The `living-adr-mcp` console script is installed with the `living-adr` package.
The `env` block carries only the config path — **no secrets**.

## Observability

Every tool call emits **metadata-only** telemetry through the feature 002
`Observability` port: tool name, repository key, status, result count, latency
bucket, and error type. Raw questions, answers, ADR bodies, citations, prompts,
graph paths, and secrets are never exported (architecture #cross-cutting,
default-deny). LangSmith export is owned by feature 013, not introduced here.

## Read-only safety summary

- No mutation, approval, publication, SCM-fetch, or config-change capability
  exists on the server.
- Every request resolves a configured `RepositoryIdentity` before any query
  runs; unknown repositories are rejected safely without leaking other
  repositories.
- Inputs are bounded (repository key, ADR id, status, question length, code
  area, snapshot id, limit) and query failures map to safe errors that never
  expose stack traces, filesystem paths, secrets, or cross-repository data.
