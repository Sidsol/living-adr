# Implementation Plan: adr-publish-back-github

## Plan Scope

Planning only. No production/application code is written by this CRISPY run. This plan describes future implementation in repository `living-adr`.

## File-Level Tactical Plan

### New/changed production paths

- `src\living_adr\publication\__init__.py` — public publication package exports.
- `src\living_adr\publication\models.py` — publication request, target, result, status, errors, fingerprint DTOs.
- `src\living_adr\publication\slugging.py` — deterministic ADR title slugging and filename-safe normalization.
- `src\living_adr\publication\numbering.py` — ADR directory scan, numeric prefix parsing, and next-number allocation.
- `src\living_adr\publication\repository.py` — SQLite publication intent/result/idempotency repository.
- `src\living_adr\publication\service.py` — approval-bound publication orchestration.
- `src\living_adr\workflow\publication_node.py` — feature 015 handoff node for approved ADR publication.
- `src\living_adr\core\scm.py` or existing SCM contract file — provider-neutral contents operations if feature 003 has not already added them.
- `src\living_adr\scm\github_provider.py` — GitHub App contents/list/commit implementation behind existing provider seam.

### New/changed test paths

- `tests\publication\test_publication_policy.py`
- `tests\publication\test_publication_repository.py`
- `tests\publication\test_publication_approval_boundary.py`
- `tests\publication\test_slugging_numbering.py`
- `tests\publication\test_publication_service.py`
- `tests\scm\test_github_provider_contents.py`
- `tests\workflow\test_publication_node.py`
- `tests\contracts\test_feature011_boundaries.py`

## Task Graph

```yaml
feature_id: "011"
slice_count: 5
tasks:
  - id: T011-S1-001
    slice: S011-01
    title: Defining publication request and target models
    files: ['src\living_adr\publication\models.py', 'tests\publication\test_publication_policy.py']
    depends_on: []
  - id: T011-S1-002
    slice: S011-01
    title: Resolving publication policy and target branch
    files: ['src\living_adr\publication\service.py', 'tests\publication\test_publication_policy.py']
    depends_on: [T011-S1-001]
  - id: T011-S1-003
    slice: S011-01
    title: Computing publication fingerprints
    files: ['src\living_adr\publication\models.py', 'tests\publication\test_publication_policy.py']
    depends_on: [T011-S1-002]
  - id: T011-S2-001
    slice: S011-02
    title: Creating publication repository records
    files: ['src\living_adr\publication\repository.py', 'tests\publication\test_publication_repository.py']
    depends_on: [T011-S1-003]
  - id: T011-S2-002
    slice: S011-02
    title: Reserving publication intent by decision
    files: ['src\living_adr\publication\repository.py', 'tests\publication\test_publication_repository.py']
    depends_on: [T011-S2-001]
  - id: T011-S2-003
    slice: S011-02
    title: Enforcing ApprovalBoundMutationService validation
    files: ['src\living_adr\publication\service.py', 'tests\publication\test_publication_approval_boundary.py']
    depends_on: [T011-S2-002]
  - id: T011-S2-004
    slice: S011-02
    title: Returning idempotent prior publication results
    files: ['src\living_adr\publication\service.py', 'tests\publication\test_publication_approval_boundary.py']
    depends_on: [T011-S2-003]
  - id: T011-S3-001
    slice: S011-03
    title: Implementing deterministic ADR slugging
    files: ['src\living_adr\publication\slugging.py', 'tests\publication\test_slugging_numbering.py']
    depends_on: [T011-S2-004]
  - id: T011-S3-002
    slice: S011-03
    title: Parsing existing ADR numeric prefixes
    files: ['src\living_adr\publication\numbering.py', 'tests\publication\test_slugging_numbering.py']
    depends_on: [T011-S3-001]
  - id: T011-S3-003
    slice: S011-03
    title: Allocating next ADR path
    files: ['src\living_adr\publication\numbering.py', 'tests\publication\test_slugging_numbering.py']
    depends_on: [T011-S3-002]
  - id: T011-S3-004
    slice: S011-03
    title: Detecting same-decision existing files
    files: ['src\living_adr\publication\numbering.py', 'tests\publication\test_slugging_numbering.py']
    depends_on: [T011-S3-003]
  - id: T011-S4-001
    slice: S011-04
    title: Extending SCM contents port
    files: ['src\living_adr\core\scm.py', 'tests\scm\test_github_provider_contents.py']
    depends_on: [T011-S3-004]
  - id: T011-S4-002
    slice: S011-04
    title: Implementing GitHub file listing and read checks
    files: ['src\living_adr\scm\github_provider.py', 'tests\scm\test_github_provider_contents.py']
    depends_on: [T011-S4-001]
  - id: T011-S4-003
    slice: S011-04
    title: Committing ADR file through GitHub provider
    files: ['src\living_adr\scm\github_provider.py', 'tests\scm\test_github_provider_contents.py']
    depends_on: [T011-S4-002]
  - id: T011-S4-004
    slice: S011-04
    title: Handling commit conflicts and provider errors
    files: ['src\living_adr\publication\service.py', 'src\living_adr\scm\github_provider.py', 'tests\publication\test_publication_service.py']
    depends_on: [T011-S4-003]
  - id: T011-S5-001
    slice: S011-05
    title: Wiring workflow publication node
    files: ['src\living_adr\workflow\publication_node.py', 'tests\workflow\test_publication_node.py']
    depends_on: [T011-S4-004]
  - id: T011-S5-002
    slice: S011-05
    title: Emitting publication audit and observability
    files: ['src\living_adr\publication\service.py', 'tests\publication\test_publication_service.py']
    depends_on: [T011-S5-001]
  - id: T011-S5-003
    slice: S011-05
    title: Adding read-side boundary tests
    files: ['tests\contracts\test_feature011_boundaries.py']
    depends_on: [T011-S5-002]
  - id: T011-S5-004
    slice: S011-05
    title: Verifying end-to-end publish-back contract
    files: ['tests\workflow\test_publication_node.py', 'tests\contracts\test_feature011_boundaries.py']
    depends_on: [T011-S5-003]
```

## Validation Commands

Future implementation should run existing project tools only:

```powershell
cd C:\repos\living-adr
uv run ruff check
uv run pytest tests\publication tests\scm\test_github_provider_contents.py tests\workflow\test_publication_node.py tests\contracts\test_feature011_boundaries.py
```

## Implementation Notes

- Do not perform provider writes until feature 010 has validated the `ApprovedReviewDecision` and target fingerprint.
- Treat local audit and remote GitHub commit as recoverable two-step work: reserve intent, call provider, finalize result; use embedded decision marker for recovery.
- Use direct commit as PoC default; keep PR mode as a future publication policy value, not hidden behavior.
- Keep SCM contents methods provider-neutral and repository-scoped.
