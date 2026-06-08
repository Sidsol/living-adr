# Quality Checklist: llamaindex-property-graph-adapter

## CRISPY Phase Gates

### 🔬 C — Research
- [ ] research.md documents the greenfield current state and notes that `C:\repos\living-adr` implementation is not present yet.
- [ ] research.md includes LlamaIndex PropertyGraphIndex construction, persistence, extractor, and retrieval specifics.
- [ ] research.md includes SQLite WAL single-writer, same-host, read concurrency, sidecar, and checkpoint considerations.
- [ ] research.md references project anchors: `..\..\architecture.md#tech-stack`, `#service-boundaries`, `#data-model`, `#cross-cutting`, and `#deployment`.
- [ ] research.md identifies feature 006 ports and conformance suite as the dependency contract.

### 🎯 R — Sound Intent
- [ ] intent.md states that feature 007 implements, and does not redefine, feature 006 ports.
- [ ] intent.md references `..\..\architecture.md#tech-stack`.
- [ ] intent.md references `..\..\architecture.md#service-boundaries`.
- [ ] intent.md references `..\..\architecture.md#data-model`.
- [ ] intent.md references `..\..\architecture.md#cross-cutting`.
- [ ] intent.md references `..\..\architecture.md#deployment`.
- [ ] Gap analysis maps current state to adapter, repository scope, persistence, schema, provenance, snapshots, conformance, and drift mitigation.
- [ ] At least 3 architecture options are evaluated.
- [ ] Selected approach has clear rationale tied to FM-08/FM-10 and the swap seam.
- [ ] Module surface analysis identifies isolated-test candidates.

### 🍕 I — Vertical Slices
- [ ] outline.md contains exactly 7 implementation slices.
- [ ] Each slice delivers end-to-end testable adapter behavior.
- [ ] Slice dependencies are mapped in text and machine-readable YAML.
- [ ] One slice explicitly runs feature 006's conformance suite green.
- [ ] Every slice includes `automation: HITL | AFK` and `automation_reason`.
- [ ] Automation classifications agree between `outline.md` and `implementation-manifest.yaml`.

### 📋 S — Tactical Plan
- [ ] Every change references a specific repo-relative file path.
- [ ] New files and modified files are clearly distinguished.
- [ ] Plan includes RED then GREEN steps for each behavior.
- [ ] Plan includes a machine-readable `task_graph` YAML block.
- [ ] Rollback strategy is documented and file-level.
- [ ] Plan does not include modifications to feature 006 port definitions.

### 🧹 P — Fresh Context
- [ ] Context reset points are identified after Slice 2, after Slice 4, and before conformance work.
- [ ] Each slice lists key files needed in context.
- [ ] State carried across slices includes repository scope, provenance, schema versioning, single-writer persistence, MCP read-only boundary, and no 006 port changes.
- [ ] No slice assumes Neo4j/Postgres/external graph database availability.

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
- [ ] Conformance is run after write/read behavior exists, not by weakening contracts early.
- [ ] Reviewers flag premature abstractions or tests for future graph backends as boundary violations.

## Feature-Specific Pre-Implementation Checks

- [ ] Feature 006 implementation exists before this feature starts.
- [ ] `ArchitectureGraphStore`, `ArchitectureContextQuery`, `ApprovalBoundMutationService`, `ADRRecord`, `ApprovedReviewDecision`, and conformance suite are consumed from feature 006.
- [ ] `LlamaIndexPropertyGraphAdapter` implements both graph ports without changing signatures.
- [ ] Feature 006 conformance suite passes against the LlamaIndex adapter fixture.
- [ ] Repository-scoped nodes are persisted and cross-repository reads are rejected or filtered.
- [ ] Schema-version metadata is created, read, checked, and migration behavior is deterministic.
- [ ] Graph files live under `var\graph` with deterministic repository partitioning.
- [ ] SQLite/WAL-compatible assumptions are documented and tested where SQLite state is used: same host, single writer, short read transactions, busy/stale handling.
- [ ] Every extracted entity and edge records provenance: ADR id, evidence id/path, decision id, extraction method, extraction timestamp, repository, and schema version.
- [ ] MCP read snapshots are available through `GraphSnapshotRef` and `validate_snapshot_current`.
- [ ] MCP-facing query methods return only domain DTOs with citations and no write handles.
- [ ] Drift/false-edge mitigation rejects or quarantines unsupported labels before current graph persistence.
- [ ] `check_conformance(repository)` reports missing provenance, schema mismatch, orphan edges, unsupported labels, and repository mismatch.

## Source-Learning Traceability Checks

- [ ] FM-08 graph schema drift is mitigated by schema-version metadata and migration/conformance hooks.
- [ ] FM-10 false edges are mitigated by strict label validation and required provenance.
- [ ] FM-09 similarity-not-causality is mitigated by returning graph paths and approved ADR citations.
- [ ] FM-11 low faithfulness is mitigated by MCP answers citing approved ADR/evidence.
- [ ] FM-13 excessive agency is mitigated by keeping writes behind `ApprovalBoundMutationService` and approved decisions.
- [ ] FM-15/FM-16 MCP trust/auth risks are mitigated by read-only query port and no mutation credentials.
- [ ] FM-21 trace leakage is mitigated by metadata-only diagnostics and no raw export by default.
- [ ] Public-agent/MCP boundary documentation preserves read-only access and no SCM credential exposure.

## Artifact Consistency Checks

- [ ] spec.md success criteria mention 006 conformance, repo-scoped nodes, schema-version metadata, WAL/single-writer, provenance, and MCP snapshots.
- [ ] research.md, intent.md, outline.md, plan.md, tasks.md, checklist.md, and implementation-manifest.yaml all use slice count 7.
- [ ] plan.md task IDs TASK-001 through TASK-023 match tasks.md.
- [ ] implementation-manifest.yaml lists all 8 planning artifacts.
- [ ] implementation-manifest.yaml `ready` matches the readiness rationale.

## Implementation Checks (per task)

- [ ] Task matches the plan; no scope creep into features 008, 010, 012, or 015.
- [ ] Tests are written before or alongside implementation.
- [ ] No unrelated files are changed.
- [ ] Code follows observed project tooling: Python 3.12, pytest, Ruff, uv.
- [ ] Checkpoint criteria from outline.md are met before marking a slice complete.
- [ ] `uv run pytest` passes.
- [ ] `uv run ruff check` passes.