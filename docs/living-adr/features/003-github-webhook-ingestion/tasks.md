# Task Breakdown: github-webhook-ingestion

## Legend

- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ✅ Not started | 🔵 In progress | ✅ Done | ❌ Blocked
- Tasks follow TDD behavior ordering: RED test first, GREEN implementation next, then integration/export where needed.

## Tasks by Story

### US-1: Verify GitHub webhook authenticity

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | RED: Add HMAC verifier tests for valid raw-body signature, body tampering, missing/malformed signature, missing delivery id, and missing event name. | ✅ | First task. |
| TASK-002 | P1 | GREEN: Implement GitHub webhook raw-byte HMAC verification and typed header extraction in `src\living_adr\scm\github_webhook.py`. | ✅ | Depends on TASK-001. |
| TASK-003 | P1 | RED: Add workflow endpoint rejection tests proving invalid signatures cause no store/provider/normalizer side effects. | ✅ | Depends on TASK-002. |
| TASK-004 | P1 | GREEN: Implement thin workflow-service webhook handler/route that verifies before JSON parsing. | ✅ | Depends on TASK-003. |
| TASK-027 | P1 | RED: Add fake end-to-end test for signed merged PR delivery producing one `SCMEvent` and candidate evidence, with duplicate delivery no-op. | ✅ | Depends on TASK-026. |
| TASK-028 | P1 | GREEN: Fix final handler/evidence/store integration gaps found by the end-to-end test. | ✅ | Depends on TASK-027. |

### US-2: Accept only configured merged PR events idempotently

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-005 | P1 | RED: Add delivery idempotency tests for first insert, duplicate prior result, conflicting duplicate metadata, and safe skipped/rejected states. | ✅ | Depends on TASK-004. |
| TASK-006 | P1 | GREEN: Implement ingestion delivery state models, statuses, error categories, retry/dead-letter fields, and state helpers. | ✅ | Depends on TASK-005. |
| TASK-007 | P1 | GREEN: Implement delivery id lookup/upsert and evidence cache hooks in `src\living_adr\persistence\ingestion_store.py`. | ✅ | Depends on TASK-006. |
| TASK-008 | P1 | RED: Add event filtering tests for configured merged PR, unconfigured repo, non-PR, unmerged closed PR, opened/synchronized PR, and malformed payload. | ✅ | Depends on TASK-007. |
| TASK-009 | P1 | GREEN: Implement verified JSON payload filtering and repository resolution through `LivingADRConfig`. | ✅ | Depends on TASK-008. |
| TASK-010 | P1 | GREEN: Wire delivery store idempotency into the webhook handler before downstream fetches. | ✅ | Depends on TASK-009. |

### US-3: Normalize merged PRs into provider-neutral SCMEvent records

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-011 | P1 | RED: Add `SCMEvent` contract tests for repository scope, provider delivery id, normalized PR key, PR fields, timestamps, and fetch handles. | ✅ | Depends on TASK-010. |
| TASK-012 | P1 | GREEN: Implement core `SCMEvent`, `SCMProvider`, PR metadata, changed-file, diff, and candidate-evidence contracts. | ✅ | Depends on TASK-011. |
| TASK-013 | P1 | RED: Add GitHub normalization tests proving raw payload maps to provider-neutral `SCMEvent` with opaque provider metadata. | ✅ | Depends on TASK-012. |
| TASK-014 | P1 | GREEN: Implement GitHub accepted-event to `SCMEvent` normalizer and normalized PR key derivation. | ✅ | Depends on TASK-013. |
| TASK-015 | P1 | Export SCM contracts and GitHub adapter helpers from package `__init__` files if project conventions require exports. | ✅ | Depends on TASK-014. |

### US-4: Fetch minimal PR/diff evidence for classifiers

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-016 | P1 | RED: Add fake GitHub provider tests for PR metadata, changed files, diff/handle, permission, rate-limit, missing PR, and transient failure. | ✅ | Depends on TASK-015. |
| TASK-017 | P1 | GREEN: Implement `GitHubProvider` behind `SCMProvider` with fakeable client seam and provider-error mapping. | ✅ | Depends on TASK-016. |
| TASK-018 | P1 | RED: Add candidate evidence tests linking `SCMEvent`, PR metadata, changed files, diff summary/handle, delivery id, normalized PR key, and provenance. | ✅ | Depends on TASK-017. |
| TASK-019 | P1 | GREEN: Implement evidence builder and evidence cache/store updates without duplicate API work. | ✅ | Depends on TASK-018. |
| TASK-020 | P1 | GREEN: Wire evidence collection into webhook handler and update delivery status for downstream classifier handoff. | ✅ | Depends on TASK-019. |

### US-5: Support replay, dead-letter handling, and observability

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-021 | P1 | RED: Add replay/dead-letter tests for retryable failure, poison event, accepted replay, recovered provider replay, and duplicate replay idempotency. | ✅ | Depends on TASK-020. |
| TASK-022 | P1 | GREEN: Implement replay service over stored delivery/event/evidence records using the same normalizer/provider/evidence builder. | ✅ | Depends on TASK-021. |
| TASK-023 | P1 | GREEN: Implement retry count, next action, dead-letter status, and error-category transition helpers in core/store. | ✅ | Depends on TASK-022. |
| TASK-024 | P1 | GREEN: Add operator replay callable/CLI-compatible entry point under workflow-service conventions. | ✅ | Depends on TASK-023. |
| TASK-025 | P1 | RED: Add observability tests proving allowed metadata for verify/duplicate/skipped/accepted/failure/replay/dead-letter and excluding raw body/diff/secrets. | ✅ | Depends on TASK-024. |
| TASK-026 | P1 | GREEN: Add metadata-only instrumentation through Feature 002 `Observability` port across webhook, provider, evidence, replay, and dead-letter paths. | ✅ | Depends on TASK-025. |

## Infrastructure / Cross-Cutting

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-029 | P1 | Run existing pytest command for all new ingestion tests and fix only feature-caused failures. | ✅ | Depends on TASK-028; verification only. |
| TASK-030 | P1 | Run existing Ruff command and confirm workflow-facing modules avoid raw GitHub payload traversal and raw observability exports. | ✅ | Depends on TASK-028; can run alongside TASK-029. |

## Execution Order

1. **Security boundary:** TASK-001 → TASK-002 → TASK-003 → TASK-004.
2. **Delivery filtering and idempotency:** TASK-005 → TASK-006 → TASK-007 → TASK-008 → TASK-009 → TASK-010.
3. **Normalized contracts:** TASK-011 → TASK-012 → TASK-013 → TASK-014 → TASK-015.
4. **Evidence fetch:** TASK-016 → TASK-017 → TASK-018 → TASK-019 → TASK-020.
5. **Replay/dead-letter:** TASK-021 → TASK-022 → TASK-023 → TASK-024.
6. **Observability and E2E:** TASK-025 → TASK-026 → TASK-027 → TASK-028.
7. **Verification:** TASK-029 and TASK-030.

## Parallel Opportunities

- This feature is intentionally mostly sequential because each slice depends on the previous trust/idempotency/contract boundary.
- TASK-029 and TASK-030 can run in parallel after TASK-028 if CI supports concurrent test/lint jobs.
- During implementation, test authoring for later slices should not start before the corresponding upstream contract exists; avoid horizontal slicing across behaviors.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 30 | 4-6 focused implementation sessions |
| P2 | 0 | 0 |
| P3 | 0 | 0 |
