# CLAUDE.md

This file points Claude (and Claude Code) at the canonical agent guidance for
this repository.

👉 **See [AGENTS.md](./AGENTS.md)** for the full guide, including:

- What LivingADR is and its two deployables.
- **How to use the `living-adr-mcp` read-only MCP server** (tools `list_adrs`,
  `fetch_adr`, `answer_why`), when to call it, and how it's connected.
- How to build, test, lint, and configure the project.
- Safety invariants that must not be broken.

Quick MCP summary: the `living-adr` MCP server exposes **approved** architecture
decision context read-only over stdio. Use `answer_why` /
`list_adrs` / `fetch_adr` against repository key `github.com/Sidsol/living-adr`
to ground architectural decisions in cited ADRs. It cannot mutate, approve, or
publish anything. Full details and host configuration are in
[AGENTS.md](./AGENTS.md) and `docs/mcp-context-server.md`.
