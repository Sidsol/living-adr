# Task Breakdown: dependency-change-detection

## Legend

- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ⬜ Not started | 🔵 In progress | ✅ Done | ❌ Blocked
- Task IDs align with `plan.md` machine-readable task graph.

## Tasks by Story

### US-1: Detect dependency manifest additions and removals

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-004 | P1 | Write RED tests for dependency manifest/lockfile recognition and path normalization. | ✅ | Slice S-002; depends on TASK-003. |
| TASK-006 | P1 | Write RED tests for direct dependency add/remove/version classification and dedupe. | ✅ | Slice S-003; depends on TASK-005. |
| TASK-007 | P1 | Implement draft-eligible direct dependency classifier and confidence scorer. | ✅ | Slice S-003; depends on TASK-006. |

### US-2: Normalize dependency evidence for downstream drafting

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | Write RED contract tests for `StructuralChange` and `ChangeEvidence` serialization/stable ids. | ✅ | Slice S-001. |
| TASK-002 | P1 | Implement `StructuralChange`, `ChangeEvidence`, stable id/hash helpers, and validation. | ✅ | Slice S-001; depends on TASK-001. |
| TASK-005 | P1 | Implement dependency evidence summaries with source paths, provenance, parser version, and immutable hash. | ✅ | Shared with US-1. |

### US-3: Suppress low-signal dependency churn

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-008 | P1 | Write RED tests for lockfile-only, unsupported, malformed, empty, and below-threshold no-ADR outcomes. | ✅ | Slice S-004; depends on TASK-007. |
| TASK-009 | P1 | Implement no-ADR-needed reason codes and low-confidence suppression. | ✅ | Slice S-004; depends on TASK-008. |

### US-4: Keep classification deterministic and replayable

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-010 | P1 | Write RED producer replay tests for identical serialized output across repeated calls. | ✅ | Slice S-005; depends on TASK-009. |
| TASK-012 | P1 | Write RED telemetry redaction tests for metadata-only classification events. | ✅ | Slice S-005; depends on TASK-011. |
| TASK-013 | P1 | Implement metadata-only classification event builder. | ✅ | Slice S-005; depends on TASK-012. |

### US-5: Integrate as the first structural-change producer

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-003 | P1 | Define generic structural-change producer protocol/result shape. | ✅ | Slice S-001; depends on TASK-002. |
| TASK-011 | P1 | Implement dependency change producer facade for Feature 015/008 handoff. | ✅ | Slice S-005; depends on TASK-010. |
| TASK-014 | P1 | Wire metadata-only telemetry into dependency change producer facade. | ✅ | Slice S-005; depends on TASK-013. |

## Execution Order

1. **S-001 Contract foundation:** TASK-001 → TASK-002 → TASK-003.
2. **S-002 Evidence recognition:** TASK-004 → TASK-005.
3. **S-003 Draft classification:** TASK-006 → TASK-007.
4. **S-004 No-ADR suppression:** TASK-008 → TASK-009.
5. **S-005 Producer integration:** TASK-010 → TASK-011 → TASK-012 → TASK-013 → TASK-014.

## Parallel Opportunities

No same-feature tasks are marked parallel-safe in this plan. The feature is intentionally sequential because each slice builds on a shared contract and threshold semantics. At project level, Feature 004 remains parallelizable with other W2 features after Feature 003 lands, subject to file conflict checks.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 14 | ~18-24 focused hours |
| P2 | 0 | 0 |
| P3 | 0 | 0 |

## TDD Notes

- Each behavior is ordered RED→GREEN within its slice.
- Avoid writing future behavior tests before the slice that owns that behavior.
- Keep fixtures local, deterministic, and independent of live GitHub/Claude/graph services.

