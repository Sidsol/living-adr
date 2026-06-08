# Task Breakdown: walking-skeleton-smoke

## Legend
- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ⬜ Not started | 🔵 In progress | ✅ Done | ❌ Blocked
- Task IDs align with `plan.md` task graph.

## Tasks by Story

### US-1: Replay a merged-PR-like event

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | Write RED replay tests for fixture normalization, repository scope, delivery id, and duplicate behavior. | ✅ | Slice SL-001. |
| TASK-002 | P1 | Create minimal project scaffold and core `RepositoryIdentity` / `SCMEvent` models. | ✅ | Depends on TASK-001. |
| TASK-003 | P1 | Implement seeded replay fixture and workflow-service smoke entrypoint. | ✅ | Depends on TASK-002. |

### US-2: Produce a deterministic stub ADR draft

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-004 | P1 | Write RED tests for deterministic structural-change classification and stub ADR draft content. | ✅ | Depends on TASK-003; Slice SL-002. |
| TASK-005 | P1 | Extend core models with `StructuralChange`, `ChangeEvidence`, and `ADRDraft`. | ✅ | Depends on TASK-004. |
| TASK-006 | P1 | Implement deterministic smoke classifier and ADR draft renderer with evidence citations and stub labeling. | ✅ | Depends on TASK-005. |

### US-3: Accept through stub HITL and persist only after approval

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-007 | P1 | Write RED tests for stub accept decision fields, content hash, reviewer id, and repository mismatch rejection. | ✅ | Depends on TASK-006; Slice SL-003. |
| TASK-008 | P1 | Extend core models with `ApprovalEvent` and `ApprovedReviewDecision` smoke fields. | ✅ | Depends on TASK-007. |
| TASK-009 | P1 | Implement accept-only stub HITL review that returns an approved decision object. | ✅ | Depends on TASK-008. |
| TASK-010 | P1 | Write RED tests proving unauthorized persistence fails and approved persistence succeeds. | ✅ | Depends on TASK-009; Slice SL-004. |
| TASK-011 | P1 | Extend core models with `ADRRecord`, citation/provenance fields, and minimal `WhyAnswer`. | ✅ | Depends on TASK-010. |
| TASK-012 | P1 | Implement approval-bound stub store and event-to-approved-record E2E persistence test. | ✅ | Depends on TASK-011. |

### US-4: Answer one MCP-style why query from approved context

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-013 | P1 | Write RED tests for approved-only MCP-style `answer_why` response and no-approved-context behavior. | ✅ | Depends on TASK-012; Slice SL-005. |
| TASK-014 | P1 | Implement read-only MCP-style `answer_why_smoke` wrapper over approved-context query logic. | ✅ | Depends on TASK-013. |
| TASK-015 | P1 | Add full walking-skeleton smoke E2E test for replay -> draft -> accept -> persist -> answer. | ✅ | Depends on TASK-014. |

## Infrastructure / Cross-Cutting

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-002 | P1 | Minimal scaffold and package configuration. | ⬜ | Listed under US-1 because it is required by replay tests. |
| TASK-012 | P1 | Approval-bound mutation guard. | ⬜ | Listed under US-3; safety-critical seam. |
| TASK-014 | P1 | Read-only MCP boundary. | ⬜ | Listed under US-4; must not import workflow write dependencies. |

## Execution Order
1. **SL-001:** TASK-001 -> TASK-002 -> TASK-003.
2. **SL-002:** TASK-004 -> TASK-005 -> TASK-006.
3. **SL-003:** TASK-007 -> TASK-008 -> TASK-009.
4. **SL-004:** TASK-010 -> TASK-011 -> TASK-012.
5. **SL-005:** TASK-013 -> TASK-014 -> TASK-015.

## Parallel Opportunities
- None planned for first implementation. The dependency chain is intentionally sequential to preserve walking-skeleton behavior ordering.
- Within a later implementation session, read-only review of prior slices can occur in parallel with RED test authoring only if it does not modify shared files.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 15 | 9-14 hours |
| P2 | 0 | 0 |
| P3 | 0 | 0 |

## TDD Notes
- Each behavior starts with a RED test task immediately followed by the model/implementation tasks needed to make that behavior GREEN.
- Do not write all tests for later slices up front; preserve no-horizontal-slicing behavior order.
- Negative tests are required for duplicate replay, missing approval decision, repository mismatch, and no-approved-context query.
