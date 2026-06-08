# Task Breakdown: claude-adr-drafting-capability

## Summary
- Slice count: 7
- Task count: 23
- Priority: all P1
- Execution style: TDD, fake dependencies, no production code in this planning phase.

## US-1: Grounded ADR draft generation
| ID | Slice | Task | Status |
|---|---|---|---|
| TASK-001 | S-001 | Write RED draft contract tests for provisional draft fields, citations, model metadata, and content hash. | ✅ |
| TASK-002 | S-001 | Implement `ADRDraft` / draft record DTOs and content hashing. | ✅ |
| TASK-011 | S-004 | Write RED prompt assembly tests for Feature 004 evidence, graph citations, ADR template, provisional labels, and delimiters. | ✅ |
| TASK-012 | S-004 | Implement ADR prompt assembler. | ✅ |
| TASK-015 | S-005 | Write RED draft parser tests for required ADR sections and citations. | ✅ |
| TASK-016 | S-005 | Implement Markdown ADR output parser and validator. | ✅ |

## US-2: Architecture context retrieval
| ID | Slice | Task | Status |
|---|---|---|---|
| TASK-007 | S-003 | Write RED graph context packaging tests using fake `ArchitectureContextQuery`. | ✅ |
| TASK-008 | S-003 | Implement graph context packer and citation DTOs. | ✅ |

## US-3: Per-repository LLM policy
| ID | Slice | Task | Status |
|---|---|---|---|
| TASK-005 | S-002 | Write RED policy tests for allow/deny, no-call-on-deny, and safe metadata. | ✅ |
| TASK-006 | S-002 | Implement repository external-LLM policy evaluator. | ✅ |

## US-4: Token-budgeted prompt packing
| ID | Slice | Task | Status |
|---|---|---|---|
| TASK-009 | S-004 | Write RED token budget tests for default, prioritization, truncation, and blocking. | ✅ |
| TASK-010 | S-004 | Implement deterministic token budgeter. | ✅ |

## US-5: Fake-client test seam
| ID | Slice | Task | Status |
|---|---|---|---|
| TASK-003 | S-001 | Write RED fake Claude client tests with call assertions and no network dependency. | ✅ |
| TASK-004 | S-001 | Implement `ClaudeClient` protocol, request/response models, and fake client. | ✅ |
| TASK-013 | S-005 | Write RED Anthropic adapter tests using SDK mocks only. | ✅ |
| TASK-014 | S-005 | Implement Anthropic-backed Claude adapter behind `ClaudeClient`. | ✅ |

## US-6: Feature 015 draft node seam
| ID | Slice | Task | Status |
|---|---|---|---|
| TASK-017 | S-006 | Write RED draft node seam tests with fake Feature 015 state/client/query. | ✅ |
| TASK-018 | S-006 | Implement real Feature 015-compatible ADR draft node. | ✅ |
| TASK-019 | S-006 | Write RED no-mutation boundary tests. | ✅ |
| TASK-020 | S-006 | Harden draft node blocked/error routing. | ✅ |

## US-7: Metadata-only observability
| ID | Slice | Task | Status |
|---|---|---|---|
| TASK-021 | S-007 | Write RED drafting event redaction tests. | ✅ |
| TASK-022 | S-007 | Implement metadata-only drafting event builders. | ✅ |
| TASK-023 | S-007 | Wire observability into draft node. | ✅ |

## Execution Order
1. S-001: TASK-001 → TASK-002 → TASK-003 → TASK-004
2. S-002: TASK-005 → TASK-006
3. S-003: TASK-007 → TASK-008
4. S-004: TASK-009 → TASK-010 → TASK-011 → TASK-012
5. S-005: TASK-013 → TASK-014 → TASK-015 → TASK-016
6. S-006: TASK-017 → TASK-018 → TASK-019 → TASK-020
7. S-007: TASK-021 → TASK-022 → TASK-023

## TDD Rules
- Start every slice with RED tests.
- Use fake Claude client, fake graph query, fake workflow state, and SDK mocks only.
- Never add approval, graph mutation, audit durability, GitHub publication, or MCP serving behavior in this feature.
