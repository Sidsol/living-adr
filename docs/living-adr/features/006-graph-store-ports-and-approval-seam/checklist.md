# Quality Checklist: graph-store-ports-and-approval-seam

## CRISPY Phase Gates

### 🔬 C — Research
- [ ] research.md documents current scaffold objectively and notes that graph/approval modules do not exist yet.
- [ ] research.md references observed code/config files with file paths.
- [ ] research.md identifies intended architecture flows from `..\..\architecture.md#service-boundaries` without treating them as implemented code.
- [ ] Configuration and dependency observations include feature 002 `RepositoryIdentity` and `Observability` dependency.
- [ ] Technical debt items include config vocabulary mismatch and missing conformance coverage.

### 🎯 R — Sound Intent
- [ ] intent.md references `..\..\architecture.md#service-boundaries`.
- [ ] intent.md references `..\..\architecture.md#data-model`.
- [ ] intent.md references `..\..\architecture.md#cross-cutting`.
- [ ] intent.md references `..\..\architecture.md#anti-patterns`.
- [ ] Gap analysis maps current scaffold to desired graph/approval seam.
- [ ] At least 3 architecture options were evaluated.
- [ ] Selected approach emphasizes approval-bound mutation and source-of-truth hierarchy.
- [ ] Module surface analysis identifies isolated-test candidates.

### 🍕 I — Vertical Slices
- [ ] outline.md contains exactly 6 implementation slices.
- [ ] Each slice delivers end-to-end testable contract behavior.
- [ ] Slice dependencies are mapped in text and machine-readable YAML.
- [ ] Every slice includes `automation: HITL | AFK` and `automation_reason`.
- [ ] Automation classifications agree between `outline.md` and `implementation-manifest.yaml`.
- [ ] A conformance test-suite slice exists for future adapters.

### 📋 S — Tactical Plan
- [ ] Every change references a specific repo-relative file path.
- [ ] New files and modified files are clearly distinguished.
- [ ] Plan includes RED then GREEN steps for each behavior.
- [ ] Plan includes a machine-readable `task_graph` YAML block.
- [ ] Rollback strategy is documented and file-level.
- [ ] No production persistence implementation or migration is included.

### 🧹 P — Fresh Context
- [ ] Context reset points are identified between slices.
- [ ] Each slice lists key files needed in context.
- [ ] State carried across slices includes repository scope, ADR authority, graph projection, and approval-bound mutation.
- [ ] No slice assumes LlamaIndex adapter implementation exists.

### 📝 Y — Task Yield
- [ ] tasks.md is organized by user story.
- [ ] Task IDs match `plan.md` task graph.
- [ ] Every functional task has a RED test or verification task paired with implementation.
- [ ] Dependencies between tasks are explicit.
- [ ] Parallel opportunities are identified conservatively.
- [ ] Every task is completable in less than two hours or split further.

### 🧪 No Horizontal Slicing (L3)
- [ ] Multi-behavior slices identify distinct behaviors.
- [ ] Tests and implementation are ordered by behavior, not by layer.
- [ ] Conformance work follows port/service behavior rather than preceding all implementation.
- [ ] Reviewers flag premature LlamaIndex adapter assumptions as boundary violations.

## Feature-Specific Pre-Implementation Checks

- [ ] Ports defined and typed: `ArchitectureGraphStore` and `ArchitectureContextQuery`.
- [ ] Every graph write method requires `RepositoryIdentity` and `ApprovedReviewDecision`.
- [ ] `ApprovalBoundMutationService` rejects mutation without `ApprovedReviewDecision` before calling the adapter.
- [ ] Invalid approval scenarios include `None`, rejected/non-approved, repository mismatch, draft hash mismatch, and mutation fingerprint mismatch.
- [ ] `ADRRecordRepository` contract states approved ADR records are authoritative rationale.
- [ ] Graph nodes/edges are documented as projections with citations to ADR/evidence.
- [ ] Adapter conformance suite exists and is executable against an in-memory fake adapter.
- [ ] No concrete persistence, LlamaIndex, MCP, FastAPI, LangSmith, or database handle leaks through public port types.
- [ ] Read-side `ArchitectureContextQuery` exposes no mutation methods or write credentials.
- [ ] Feature 010 durability responsibilities are not implemented prematurely.

## Source-Learning Traceability Checks

- [ ] FM-06 hallucinated rationale is mitigated by requiring approved ADR linkage before mutation.
- [ ] FM-08 graph schema drift is mitigated by schema-version and conformance hooks.
- [ ] FM-10 false edges are mitigated by provenance and approval-bound mutation.
- [ ] FM-13 excessive agency is mitigated by deterministic service validation before writes.
- [ ] FM-15/FM-16 MCP trust/auth risks are mitigated by read-only query port separation.
- [ ] FM-21 trace leakage is mitigated by metadata-only observability expectations.
- [ ] FM-23 docs-as-code without review gates is mitigated by approved ADR record authority.
- [ ] Public-agent/MCP boundary documentation preserves read-only access and no SCM credential exposure.

## Implementation Checks (per task)

- [ ] Task matches the plan; no scope creep into feature 007, 010, 012, or 015.
- [ ] Tests are written before or alongside implementation.
- [ ] No unrelated files are changed.
- [ ] Code follows observed project tooling: Python 3.12, pytest, Ruff, uv.
- [ ] Checkpoint criteria from outline.md are met before marking a slice complete.
- [ ] `uv run pytest` passes.
- [ ] `uv run ruff check` passes.
