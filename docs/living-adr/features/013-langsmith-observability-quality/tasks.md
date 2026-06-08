# Task Breakdown: langsmith-observability-quality

## Legend

- **P1** = Must-have | **P2** = Should-have | **P3** = Nice-to-have
- ⬜ Not started | 🔵 In progress | ✅ Done | ❌ Blocked

## Tasks by Story

### US-1: Emit metadata-only LangSmith traces

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-001 | P1 | Define LangSmith observability settings in `src\living_adr\observability\config.py`. | ⬜ | Start with disabled/no-op and raw export false defaults. |
| TASK-002 | P1 | Implement `LangSmithObservability` behind feature 002's `Observability` methods. | ⬜ | Depends on TASK-001; do not alter port names. |
| TASK-004 | P1 | Write fake-client adapter tests for port compatibility, no network I/O, spans, and swallowed adapter failures. | ⬜ | Depends on TASK-002 and TASK-003. |
| TASK-005 | P1 | Implement default-deny redaction policy and forbidden raw metadata keys. | ⬜ | Depends on TASK-004. |
| TASK-006 | P1 | Add safe structured logging for events, counters, spans, and redaction diagnostics. | ⬜ | Depends on TASK-005. |
| TASK-007 | P1 | Wire redaction and safe logging into the LangSmith adapter before client export. | ⬜ | Depends on TASK-005 and TASK-006. |
| TASK-008 | P1 | Write redaction tests for raw diffs, prompts, drafts, reviewer comments, retrieved context, code snippets, secrets, nested values, debug raw export, and sensitive repos. | ⬜ | Depends on TASK-007. |

### US-2: Measure latency and token-count quality signals

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-009 | P1 | Define latency, token-count, retry, and error-type metric helpers in `src\living_adr\observability\metrics.py`. | ⬜ | Depends on TASK-008. |
| TASK-010 | P1 | Write metric helper tests for safe metadata shape, numeric token counts, latency units, repository scope, and redaction compatibility. | ⬜ | Depends on TASK-009. |

### US-3: Track draft outcomes and unauthorized-mutation checks

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-011 | P1 | Add draft outcome and mutation authorization event helpers in `src\living_adr\observability\decisions.py`. | ⬜ | Depends on TASK-008; can run in parallel with TASK-009 after Slice 2. |
| TASK-012 | P1 | Write decision/mutation tests for SM-01 and SM-05 event names, reason codes, and safe identifiers only. | ⬜ | Depends on TASK-011. |

### US-4: Provide retrieval and drafting evaluation harness

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-013 | P1 | Define versioned retrieval and drafting fixture schemas in `src\living_adr\observability\evals\fixtures.py`. | ⬜ | Depends on TASK-010 and TASK-012. |
| TASK-014 | P1 | Implement retrieval evaluator for SM-03/SM-04 expected citation and coverage checks. | ⬜ | Depends on TASK-013. |
| TASK-015 | P1 | Implement drafting evaluator for evidence citation, alternatives, consequences, and provisional-rationale checks. | ⬜ | Depends on TASK-013. |
| TASK-016 | P1 | Add evaluation runner plus example held-out query and drafting fixtures. | ⬜ | Depends on TASK-014 and TASK-015. |
| TASK-017 | P1 | Write evaluation tests with fake query/draft adapters and machine-readable pass/fail/regression output assertions. | ⬜ | Depends on TASK-016. |

### US-5: Configure retention, sampling, and safe local defaults

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| TASK-003 | P2 | Add adapter factory and workflow/MCP bootstrap helpers that select LangSmith only when configured and otherwise preserve no-op behavior. | ⬜ | Depends on TASK-001 and TASK-002; sampling/retention/raw-export metadata conventions are covered by TASK-009 under US-2. |

## Infrastructure / Cross-Cutting

| ID | Pri | Task | Status | Notes |
|---|---|---|---|---|
| CHECK-001 | P1 | Verify fake-client tests do not need live LangSmith credentials. | ⬜ | Cross-cuts Slice 1; satisfied by TASK-004. |
| CHECK-002 | P1 | Verify metadata-only traces and default-deny raw export are enforced in tests. | ⬜ | Cross-cuts Slice 2; satisfied by TASK-008. |
| CHECK-003 | P1 | Verify evaluation output is suitable for CI/local regression review. | ⬜ | Cross-cuts Slice 5; satisfied by TASK-017. |

## Execution Order

1. **Sequential foundation:** TASK-001 → TASK-002 → TASK-003 → TASK-004.
2. **Sequential safety boundary:** TASK-005 → TASK-006 → TASK-007 → TASK-008.
3. **Parallel Group A:** TASK-009 and TASK-011 after TASK-008.
4. **Parallel Group B:** TASK-010 after TASK-009, and TASK-012 after TASK-011.
5. **Sequential eval foundation:** TASK-013 after TASK-010 and TASK-012.
6. **Behavior branches:** TASK-014 and TASK-015 may be implemented after TASK-013, but merge through TASK-016.
7. **Final verification:** TASK-017 after TASK-016.

## Parallel Opportunities

- TASK-009 and TASK-011: different helper modules after shared redaction policy is complete.
- TASK-010 and TASK-012: different test files and no shared writes after their helper modules exist.
- TASK-014 and TASK-015: retrieval and drafting evaluator modules can be implemented independently after fixture schemas are stable, but plan conservatively serializes runner integration.

## Estimation Summary

| Priority | Count | Estimated Total |
|---|---:|---|
| P1 | 16 | 24-32 hours |
| P2 | 1 | 2-3 hours |
| P3 | 0 | 0 hours |

## TDD RED → GREEN Notes

- For each task that creates a behavior, write or update its pytest file first and observe RED before implementation.
- Keep behavior order local: adapter behavior tests before adapter implementation completion; redaction tests before policy completion; metric tests before helper finalization; eval output tests before runner completion.
- Avoid horizontal slicing such as writing all tests for all future slices at once.
