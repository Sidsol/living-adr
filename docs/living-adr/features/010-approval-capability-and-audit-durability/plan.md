# Implementation Plan: approval-capability-and-audit-durability

## Plan Scope

Planning only. No production/application code is written by this CRISPY run. This file gives the tactical implementation plan for future implementation in repository `living-adr`.

## File-Level Tactical Plan

### New/changed production paths

- `src\living_adr\approval\__init__.py` — public approval package exports.
- `src\living_adr\approval\models.py` — `ApprovalEvent`, `ApprovedReviewDecision`, consumption DTOs, validation errors.
- `src\living_adr\approval\hashing.py` — canonical ADR content hashing helper.
- `src\living_adr\approval\repository.py` — approval/audit repository protocol and SQLite implementation.
- `src\living_adr\approval\minting.py` — review resume command to capability minting service.
- `src\living_adr\approval\validation.py` — TTL, scope, target fingerprint, approval state, and hash validation.
- `src\living_adr\approval\mutation_service.py` — `ApprovalBoundMutationService` and authorized graph mutation orchestration.
- `src\living_adr\approval\audit_queries.py` — SM-05 and downstream decision/mutation audit queries.
- `src\living_adr\workflow\approval_node.py` — feature 015 seam adapter for minting and attaching approved decisions.

### New/changed test paths

- `tests\approval\test_approval_event_repository.py`
- `tests\approval\test_approved_decision_minting.py`
- `tests\approval\test_approval_validation.py`
- `tests\approval\test_decision_consumption.py`
- `tests\approval\test_audit_queries.py`
- `tests\approval\test_approval_bound_mutation_service.py`
- `tests\workflow\test_approval_resume_integration.py`
- `tests\contracts\test_feature011_approval_contract.py`

## Task Graph

```yaml
feature_id: "010"
slice_count: 7
tasks:
  - id: T010-S1-001
    slice: S010-01
    title: Defining approval event models
    files: ["src\living_adr\approval\models.py", "tests\approval\test_approval_event_repository.py"]
    depends_on: []
  - id: T010-S1-002
    slice: S010-01
    title: Creating durable approval repository
    files: ["src\living_adr\approval\repository.py", "tests\approval\test_approval_event_repository.py"]
    depends_on: [T010-S1-001]
  - id: T010-S1-003
    slice: S010-01
    title: Recording all review outcomes
    files: ["src\living_adr\approval\minting.py", "tests\approval\test_approval_event_repository.py"]
    depends_on: [T010-S1-002]
  - id: T010-S2-001
    slice: S010-02
    title: Defining approved decision contract
    files: ["src\living_adr\approval\models.py", "tests\approval\test_approved_decision_minting.py"]
    depends_on: [T010-S1-003]
  - id: T010-S2-002
    slice: S010-02
    title: Implementing canonical ADR hashing
    files: ["src\living_adr\approval\hashing.py", "tests\approval\test_approved_decision_minting.py"]
    depends_on: [T010-S2-001]
  - id: T010-S2-003
    slice: S010-02
    title: Minting approved capabilities
    files: ["src\living_adr\approval\minting.py", "tests\approval\test_approved_decision_minting.py"]
    depends_on: [T010-S2-002]
  - id: T010-S3-001
    slice: S010-03
    title: Adding TTL validation
    files: ["src\living_adr\approval\validation.py", "tests\approval\test_approval_validation.py"]
    depends_on: [T010-S2-003]
  - id: T010-S3-002
    slice: S010-03
    title: Adding repository and target validation
    files: ["src\living_adr\approval\validation.py", "tests\approval\test_approval_validation.py"]
    depends_on: [T010-S3-001]
  - id: T010-S3-003
    slice: S010-03
    title: Detecting draft content tampering
    files: ["src\living_adr\approval\validation.py", "tests\approval\test_approval_validation.py"]
    depends_on: [T010-S3-002]
  - id: T010-S4-001
    slice: S010-04
    title: Designing consumption records
    files: ["src\living_adr\approval\models.py", "src\living_adr\approval\repository.py", "tests\approval\test_decision_consumption.py"]
    depends_on: [T010-S3-003]
  - id: T010-S4-002
    slice: S010-04
    title: Recording atomic consumption
    files: ["src\living_adr\approval\repository.py", "tests\approval\test_decision_consumption.py"]
    depends_on: [T010-S4-001]
  - id: T010-S4-003
    slice: S010-04
    title: Supporting idempotent retry
    files: ["src\living_adr\approval\mutation_service.py", "tests\approval\test_decision_consumption.py"]
    depends_on: [T010-S4-002]
  - id: T010-S4-004
    slice: S010-04
    title: Rejecting decision reuse
    files: ["src\living_adr\approval\validation.py", "tests\approval\test_decision_consumption.py"]
    depends_on: [T010-S4-003]
  - id: T010-S5-001
    slice: S010-05
    title: Writing audit event taxonomy
    files: ["src\living_adr\approval\models.py", "tests\approval\test_audit_queries.py"]
    depends_on: [T010-S4-004]
  - id: T010-S5-002
    slice: S010-05
    title: Persisting validation failure audits
    files: ["src\living_adr\approval\repository.py", "src\living_adr\approval\validation.py", "tests\approval\test_audit_queries.py"]
    depends_on: [T010-S5-001]
  - id: T010-S5-003
    slice: S010-05
    title: Building SM05 audit queries
    files: ["src\living_adr\approval\audit_queries.py", "tests\approval\test_audit_queries.py"]
    depends_on: [T010-S5-002]
  - id: T010-S5-004
    slice: S010-05
    title: Separating audit from checkpoints
    files: ["tests\approval\test_audit_queries.py", "tests\workflow\test_approval_resume_integration.py"]
    depends_on: [T010-S5-003]
  - id: T010-S6-001
    slice: S010-06
    title: Defining mutation service interface
    files: ["src\living_adr\approval\mutation_service.py", "tests\approval\test_approval_bound_mutation_service.py"]
    depends_on: [T010-S5-004]
  - id: T010-S6-002
    slice: S010-06
    title: Delegating graph writes through service
    files: ["src\living_adr\approval\mutation_service.py", "tests\approval\test_approval_bound_mutation_service.py"]
    depends_on: [T010-S6-001]
  - id: T010-S6-003
    slice: S010-06
    title: Preventing direct graph mutation
    files: ["tests\approval\test_approval_bound_mutation_service.py", "tests\workflow\test_approval_resume_integration.py"]
    depends_on: [T010-S6-002]
  - id: T010-S6-004
    slice: S010-06
    title: Preserving adapter neutrality
    files: ["src\living_adr\approval\mutation_service.py", "tests\approval\test_approval_bound_mutation_service.py"]
    depends_on: [T010-S6-003]
  - id: T010-S7-001
    slice: S010-07
    title: Wiring workflow approval node
    files: ["src\living_adr\workflow\approval_node.py", "tests\workflow\test_approval_resume_integration.py"]
    depends_on: [T010-S6-004]
  - id: T010-S7-002
    slice: S010-07
    title: Passing capability to mutation handoff
    files: ["src\living_adr\workflow\approval_node.py", "tests\workflow\test_approval_resume_integration.py"]
    depends_on: [T010-S7-001]
  - id: T010-S7-003
    slice: S010-07
    title: Documenting feature011 publish boundary
    files: ["tests\contracts\test_feature011_approval_contract.py", "src\living_adr\approval\models.py"]
    depends_on: [T010-S7-002]
  - id: T010-S7-004
    slice: S010-07
    title: Verifying end-to-end approval durability
    files: ["tests\workflow\test_approval_resume_integration.py", "tests\contracts\test_feature011_approval_contract.py"]
    depends_on: [T010-S7-003]
```

## Validation Commands

Future implementation should run existing project tools only:

```powershell
cd C:\repos\living-adr
uv run ruff check
uv run pytest tests\approval tests\workflow\test_approval_resume_integration.py tests\contracts\test_feature011_approval_contract.py
```

## Implementation Notes

- Treat audit writes as fail-closed prerequisites to capability minting and consumption.
- Use injectable clock and UUID providers in tests for deterministic TTL and id generation.
- Keep `ApprovedReviewDecision` serializable so feature 015 can carry it in workflow state, but keep authoritative persistence in approval audit tables.
- Use feature 007/006 ports only; no LlamaIndex imports in approval code.
