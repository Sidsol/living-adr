# CRISPY Checklist: mcp-context-server

## Scope Gates

- [ ] Feature remains limited to the read-only MCP context server.
- [ ] No production/application code is written during this planning run.
- [ ] Implementation excludes graph writes, SCM credentials, Claude calls, HITL actions, publish-back, HTTP/OAuth MCP, and broad IDE extension UX.

## Contract Gates

- [ ] MCP handlers depend on feature 007/006 `ArchitectureContextQuery` only for graph access.
- [ ] No MCP code redefines `ArchitectureGraphStore`, `ArchitectureContextQuery`, `RepositoryIdentity`, `ADRRef`, `WhyAnswer`, or `ProvenancedADR`.
- [ ] MCP app binds to feature 002 `LivingADRConfig`, `RepositoryIdentity`, startup diagnostics, and `Observability` port.
- [ ] No direct LlamaIndex, SQLite handle, storage context, GitHub provider, Claude client, `ApprovalBoundMutationService`, or write-side graph dependency crosses into MCP handlers.

## Read-Only Safety Gates

- [ ] Capability enumeration contains only read-only context surfaces.
- [ ] Forbidden operations (`approve`, `edit`, `reject`, `publish`, `upsert`, `migrate`, `rebuild`, `supersede`, `retract`, SCM fetch) are absent.
- [ ] Tests prove malicious or accidental mutation requests cannot be satisfied through MCP.
- [ ] The server starts without write credentials.

## Repository Scope Gates

- [ ] Every request resolves a configured `RepositoryIdentity` before query execution.
- [ ] Unknown repository keys are rejected safely.
- [ ] Cross-repository ADR id collisions do not leak data.
- [ ] Single-repo PoC uses the same list-based configuration path as multi-repo configurations.

## Response Quality Gates

- [ ] `list_adrs` returns scoped `ADRRef` data and handles empty/filtered results.
- [ ] `fetch_adr` returns `ProvenancedADR` content and citations without internal type leakage.
- [ ] `answer_why` returns cited `WhyAnswer` data or an explicit no-approved-context result.
- [ ] Responses preserve citations/provenance to approved ADRs/evidence.
- [ ] Unsupported claims are not synthesized in MCP handlers.

## Validation and Error Gates

- [ ] Inputs are bounded for repository key, ADR id, status, question length, code area, snapshot, and limit.
- [ ] Default `answer_why` limit is 5 and maximum is 10 unless implementation documents a safer stricter value.
- [ ] Query-port exceptions are mapped to safe MCP errors.
- [ ] Safe errors do not expose secrets, raw stack traces, private filesystem details, or cross-repository data.

## Observability Gates

- [ ] MCP calls emit metadata-only events through feature 002 `Observability`.
- [ ] Metadata whitelist excludes raw ADR bodies, prompts, diffs, retrieved context, graph paths, secrets, and stack traces.
- [ ] No LangSmith dependency is introduced directly by this feature.

## Testing Gates

- [ ] Each of the 6 slices has focused tests.
- [ ] Fake `ArchitectureContextQuery` fixtures cover deterministic handler behavior.
- [ ] Startup tests cover valid and invalid feature 002 config.
- [ ] Read-only dependency tests fail if forbidden write-side modules are imported/injected.
- [ ] Tests run without GitHub, Claude, LangSmith, external graph databases, or network access.
- [ ] Existing project commands (`uv run pytest`, `uv run ruff check`) pass after implementation.

## Documentation Gates

- [ ] Local stdio MCP host configuration is documented.
- [ ] Documentation states the server is read-only and lists exposed tools/resources.
- [ ] Documentation includes no secrets and does not instruct users to provide write credentials to MCP.
- [ ] Post-PoC HTTP/OAuth/remote-hosting decisions are clearly deferred.

## Manifest Gates

- [ ] `implementation-manifest.yaml` is valid YAML.
- [ ] `ready: true` because no blocking open questions remain.
- [ ] Manifest slice count is 6 and matches `outline.md`, `plan.md`, and `tasks.md`.
- [ ] All task IDs are unique and match the task graph.
