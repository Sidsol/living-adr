# living-adr

Single local repo containing shared core code plus two deployables: `workflow-service` and `mcp-context-server`.

## Getting Started

Run `uv sync` to install dependencies, then `uv run pytest` to execute the test suite.

## Repository onboarding validation

Before expecting webhook ingestion to work, validate that the configured PoC
repository is ready:

```
uv run living-adr onboard validate --config path/to/living-adr.config.yaml
```

The check loads config through the typed config loader, verifies required
environment variables (see `.env.example` — copy it to `.env` and fill in real
values), and verifies the GitHub App installation and publication-policy
permissions for the configured repository. It prints grouped, secret-safe
diagnostics and exits non-zero when any blocking problem is found; a passing run
prints safe repository metadata and the next operational step.

This is **PoC single-repo onboarding validation** — it performs no multi-repo
governance automation, repository discovery, or hot reload. Configuration is read
at startup, so after changing config or environment values you must restart both
`living-adr-workflow` and `living-adr-mcp`.

