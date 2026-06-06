<!-- livingadr_decision_id: 722ee98a-a339-45b5-bf1b-c7d79adb7457 -->
# Add New Python Dependency via pyproject.toml

Status: proposed (PROVISIONAL — not authoritative until human approval)

## Context

A pull request against the `living-adr` repository introduces a change to `pyproject.toml`, the canonical Python dependency manifest for this project. The change reflects the direct addition of at least one new dependency (net diff: +1 line, −0 lines). The specific package name, version constraint, and dependency group (e.g., runtime, dev, optional) are not fully resolved in the available evidence — the `before`/`after` fields are recorded as `n/a` and the diff must be inspected at the referenced location (`github:/repos/Sidsol/living-adr/pulls/1.diff#pyproject.toml`) to confirm the exact package.

This ADR is raised because adding a direct dependency is an architecture-significant event: it expands the project's supply-chain surface, may introduce transitive dependencies, affects reproducibility, and can influence build, test, and deployment pipelines.

Key drivers:
- **Traceability**: Dependency additions should be recorded so future maintainers understand why a package was introduced.
- **Supply-chain hygiene**: Unreviewed additions increase vulnerability exposure.
- **Reproducibility**: Version constraints in `pyproject.toml` directly affect lock-file stability.

> ⚠️ Because no approved architecture context is configured and the diff content is partially unresolved, all rationale below is provisional and must be validated against the actual package name and version before approval.

## Decision

Accept the addition of the new direct Python dependency declared in `pyproject.toml` (PR #1), subject to the following conditions being verified by a human reviewer before this ADR is approved:

1. **Identity confirmed**: The exact package name and version constraint are inspected at `github:/repos/Sidsol/living-adr/pulls/1.diff#pyproject.toml`.
2. **Necessity justified**: The package solves a problem that cannot be addressed by an existing dependency or the standard library.
3. **Version pinned or bounded**: A minimum version (and ideally an upper bound) is specified to protect against breaking changes.
4. **License compatible**: The package license is compatible with this project's license.
5. **Actively maintained**: The package has recent releases and no known critical CVEs at the time of merge.

## Alternatives

| Alternative | Notes |
|---|---|
| **Reject the addition** | If the functionality is already available via an existing dependency or the standard library, the new package should not be added. |
| **Use an optional/extra dependency group** | If the package is only needed for a specific use case (e.g., docs, testing, a plugin), it should be placed in an `[project.optional-dependencies]` or `[dependency-groups]` section rather than the main `dependencies` list. |
| **Vendor the dependency** | For small, stable utilities with restrictive licensing concerns, vendoring (copying source into the repo) avoids supply-chain risk at the cost of maintenance burden. |
| **Defer to a later milestone** | If the feature requiring this dependency is not yet needed, the addition can be deferred to reduce immediate review burden. |

## Consequences

**Positive:**
- Enables the functionality or developer-experience improvement that motivated the addition.
- Explicit declaration in `pyproject.toml` ensures the dependency is tracked and reproducible via lock files (e.g., `uv.lock`, `poetry.lock`, `pip-compile` output).

**Negative / Risks:**
- Expands the transitive dependency graph, potentially introducing version conflicts with existing packages.
- Increases supply-chain attack surface; the new package and its transitive dependencies must be monitored for CVEs.
- If no upper-bound version constraint is set, future `pip install` or lock-file refreshes may silently pull in breaking changes.

**Follow-ups required:**
- [ ] Human reviewer must inspect the diff at `github:/repos/Sidsol/living-adr/pulls/1.diff#pyproject.toml` and confirm the package name, version constraint, and dependency group.
- [ ] Update or regenerate the project lock file after merge.
- [ ] Add the new package to any dependency-scanning configuration (e.g., Dependabot, `pip-audit` CI step).
- [ ] Document the purpose of the dependency in a code comment or `README` if it is non-obvious.

## Citations

| ID | Type | Role in this ADR |
|---|---|---|
| `3b09d510bc477ef566570e5cfb59eb93ff55e16a52e2f3c7331c4f7303fc386d` | `dependency_manifest` | Primary evidence: confirms a direct dependency was added to `pyproject.toml` in PR #1 with a net diff of +1/−0 lines. |

No approved ADR IDs were available to cite. Rationale is entirely provisional pending human review and approval.