# Task Breakdown: schema-api-contract-change-detection

## Legend

- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ⬜ Not started | 🔵 In progress | ✅ Done | ❌ Blocked

## Tasks by Story

### US-1: Detect database and schema changes

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-006 | P1 | Write RED schema detector tests for migrations, DDL, ORM fields, schema registry files, generated migrations, runtime-limited patterns, and no-change cases | ⬜ | Depends on TASK-004 |
| TASK-007 | P1 | Implement `src\living_adr\workflow\classifiers\schema.py` until schema tests pass | ⬜ | Depends on TASK-006 |
| TASK-016 | P1 | Extend fixture matrix for direct, ambiguous, generated, mixed, and no-change schema cases | ⬜ | Depends on TASK-015 |

### US-2: Detect API contract changes

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-008 | P1 | Write RED API detector tests for OpenAPI, GraphQL, protobuf/RPC, route signatures, request/response models, status/error changes, generated artifacts, and internal-only changes | ⬜ | Depends on TASK-004; can run in parallel with TASK-006 |
| TASK-009 | P1 | Implement `src\living_adr\workflow\classifiers\api_contract.py` until API tests pass | ⬜ | Depends on TASK-008 |

### US-3: Preserve a shared StructuralChange contract

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | Write RED tests proving schema/API outputs use feature 004's byte-identical `StructuralChange` / `ChangeEvidence` serialized field set | ⬜ | Start here |
| TASK-002 | P1 | Reuse or adapt `src\living_adr\core\structural_change.py` without adding/removing/renaming feature 004 contract fields | ⬜ | Depends on TASK-001; feature 004 spec/intent confirms exact contract fields |
| TASK-013 | P1 | Write RED service tests for zero/multiple outputs, mixed schema/API PRs, and compatibility with feature 008 consumer needs | ⬜ | Depends on TASK-012 |
| TASK-015 | P1 | Export stable classifier facade and policy types from `workflow\classifiers\__init__.py` | ⬜ | Depends on TASK-014 |

### US-4: Report confidence and explicit uncertainty

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-010 | P1 | Write RED confidence/uncertainty tests for direct evidence boosts, generated/runtime penalties, confidence bounds, policy versioning, default threshold `0.70`, per-repo overrides, and low-confidence retention | ⬜ | Depends on TASK-007 and TASK-009 |
| TASK-011 | P1 | Implement `confidence.py` with `ConfidencePolicy`, uncertainty reasons, scoring factors, default threshold `0.70`, per-repo overrides, and routing decisions | ⬜ | Depends on TASK-010 |
| TASK-012 | P1 | Wire schema and API detectors to shared confidence policy and record threshold/uncertainty through feature-004-compatible fields | ⬜ | Depends on TASK-011 |
| TASK-018 | P1 | Run final verification commands `uv run pytest` and `uv run ruff check` from `C:\repos\living-adr` | ⬜ | Depends on TASK-017 |

### US-5: Carry forward the threshold decision point

US-5 is implemented by TASK-010, TASK-011, and TASK-012 under US-4. Those tasks are not duplicated here so task IDs remain unique; reviewers must verify that their acceptance criteria cover the resolved `semantic-change-default-v1` policy, default threshold `0.70`, per-repository overrides, policy version recording, and no-ADR-needed retention.

### US-6: Integrate with merged-PR evidence safely

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-003 | P2 | Write RED evidence adapter tests for feature 003-like evidence, path normalization, repository mismatch, and no raw diff exposure | ⬜ | Depends on TASK-002 |
| TASK-004 | P2 | Implement `inputs.py` classifier input adapter over `SCMEvent` and candidate evidence bundle | ⬜ | Depends on TASK-003 |
| TASK-005 | P2 | Create classifier package exports for stable input/facade types | ⬜ | Depends on TASK-004 |
| TASK-014 | P2 | Implement `service.py` facade to run schema/API detectors, de-duplicate, retain low-confidence outcomes, and emit metadata-only observability | ⬜ | Depends on TASK-013 |
| TASK-017 | P2 | Verify observability metadata excludes raw diffs, raw prompts, secrets, and full source content | ⬜ | Final safety check |

## Infrastructure / Cross-Cutting

Cross-cutting requirements are carried by TASK-002, TASK-011, and TASK-018 in the story tables above. Do not create duplicate task rows; verify those tasks include feature-004-compatible contract reuse, threshold policy versioning/default `0.70`, and final test/lint verification.

## Execution Order

1. **Sequential contract foundation:** TASK-001 → TASK-002.
2. **Sequential input adapter:** TASK-003 → TASK-004 → TASK-005.
3. **Parallel detector behavior:** TASK-006 → TASK-007 and TASK-008 → TASK-009 may proceed in parallel after TASK-004.
4. **Sequential policy integration:** TASK-010 → TASK-011 → TASK-012.
5. **Sequential service facade:** TASK-013 → TASK-014 → TASK-015.
6. **Final verification:** TASK-016 → TASK-017 → TASK-018.

## Parallel Opportunities

- TASK-006 and TASK-008: independent RED tests for schema and API detectors after classifier inputs exist.
- TASK-007 and TASK-009: can proceed in parallel if file ownership is separated and confidence policy is not edited until TASK-010.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 13 | 2-3 focused days |
| P2 | 5 | 1 focused day |
| P3 | 0 | 0 |

## TDD Behavior Ordering

Within each slice, write the behavior test first, implement only that behavior, and run the targeted test before moving to the next behavior. Do not write all detector tests first and implement later; keep RED → GREEN per behavior to avoid horizontal slicing.
