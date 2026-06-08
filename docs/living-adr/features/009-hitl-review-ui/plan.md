# Tactical Plan: hitl-review-ui

## Scope
Implement planning target for feature 009 only: accessible FastAPI/Jinja2 HITL review UI that consumes feature 008 drafts and resumes feature 015 workflows. Do not implement feature 010 approval capability minting/audit durability or any graph mutation.

## File-Level Plan
| Path | Change |
|---|---|
| `src\living_adr\hitl\models.py` | Add review view model, form DTOs, validation results, allowed action constants. |
| `src\living_adr\hitl\gateway.py` | Add `ReviewWorkflowGateway` protocol/adapter around feature 015 pending review and resume services. |
| `src\living_adr\hitl\auth.py` | Add local UI token guard and signed review nonce helper. |
| `src\living_adr\hitl\hashing.py` | Add deterministic edited-draft SHA-256 helper. |
| `src\living_adr\hitl\observability.py` | Add metadata-only review event builder. |
| `src\living_adr\apps\workflow_service\hitl_routes.py` | Add GET/POST review routes using gateway, auth, validation, templates, redirects. |
| `src\living_adr\apps\workflow_service\templates\hitl\review.html` | Add accessible review form/template. |
| `src\living_adr\apps\workflow_service\templates\hitl\status.html` | Add status/error template. |
| `src\living_adr\apps\workflow_service\static\hitl.css` | Add minimal focus/error/confidence styling. |
| `tests\hitl\test_models.py` | Validate view models/actions/errors. |
| `tests\hitl\test_gateway_contract.py` | Verify mapping to feature 015 payload/command contracts. |
| `tests\hitl\test_routes.py` | Verify GET/POST route behavior with fake gateway. |
| `tests\hitl\test_accessibility_templates.py` | Verify semantic HTML, labels, headings, errors, and keyboard-friendly controls. |
| `tests\hitl\test_boundary.py` | Assert no capability minting, graph writes, Claude/GitHub calls, or raw telemetry. |

## Task Graph
```yaml
feature_id: '009'
feature_name: hitl-review-ui
slice_count: 6
task_count: 18
tasks:
  - id: T-001
    slice: SL-001
    title: Defining review view models
    files: ['src\living_adr\hitl\models.py', 'tests\hitl\test_models.py']
    depends_on: []
  - id: T-002
    slice: SL-001
    title: Creating review workflow gateway
    files: ['src\living_adr\hitl\gateway.py', 'tests\hitl\test_gateway_contract.py']
    depends_on: [T-001]
  - id: T-003
    slice: SL-001
    title: Mapping pending payload to page model
    files: ['src\living_adr\hitl\models.py', 'src\living_adr\hitl\gateway.py', 'tests\hitl\test_gateway_contract.py']
    depends_on: [T-001, T-002]
  - id: T-004
    slice: SL-002
    title: Adding review GET route
    files: ['src\living_adr\apps\workflow_service\hitl_routes.py', 'tests\hitl\test_routes.py']
    depends_on: [T-003]
  - id: T-005
    slice: SL-002
    title: Rendering draft evidence template
    files: ['src\living_adr\apps\workflow_service\templates\hitl\review.html', 'tests\hitl\test_accessibility_templates.py']
    depends_on: [T-004]
  - id: T-006
    slice: SL-002
    title: Styling accessible review states
    files: ['src\living_adr\apps\workflow_service\static\hitl.css', 'tests\hitl\test_accessibility_templates.py']
    depends_on: [T-005]
  - id: T-007
    slice: SL-003
    title: Protecting review forms
    files: ['src\living_adr\hitl\auth.py', 'tests\hitl\test_routes.py']
    depends_on: [T-004]
  - id: T-008
    slice: SL-003
    title: Submitting approve command
    files: ['src\living_adr\apps\workflow_service\hitl_routes.py', 'tests\hitl\test_routes.py']
    depends_on: [T-007]
  - id: T-009
    slice: SL-003
    title: Submitting reject command
    files: ['src\living_adr\apps\workflow_service\hitl_routes.py', 'tests\hitl\test_routes.py']
    depends_on: [T-007]
  - id: T-010
    slice: SL-004
    title: Validating edited draft content
    files: ['src\living_adr\hitl\models.py', 'tests\hitl\test_models.py']
    depends_on: [T-008]
  - id: T-011
    slice: SL-004
    title: Hashing edited draft content
    files: ['src\living_adr\hitl\hashing.py', 'tests\hitl\test_models.py']
    depends_on: [T-010]
  - id: T-012
    slice: SL-004
    title: Submitting approve-after-edit command
    files: ['src\living_adr\apps\workflow_service\hitl_routes.py', 'src\living_adr\apps\workflow_service\templates\hitl\review.html', 'tests\hitl\test_routes.py']
    depends_on: [T-010, T-011]
  - id: T-013
    slice: SL-005
    title: Submitting defer command
    files: ['src\living_adr\apps\workflow_service\hitl_routes.py', 'tests\hitl\test_routes.py']
    depends_on: [T-007]
  - id: T-014
    slice: SL-005
    title: Rendering status pages
    files: ['src\living_adr\apps\workflow_service\templates\hitl\status.html', 'tests\hitl\test_routes.py']
    depends_on: [T-008, T-009, T-013]
  - id: T-015
    slice: SL-005
    title: Handling missing unauthorized states
    files: ['src\living_adr\apps\workflow_service\hitl_routes.py', 'src\living_adr\apps\workflow_service\templates\hitl\status.html', 'tests\hitl\test_routes.py']
    depends_on: [T-014]
  - id: T-016
    slice: SL-006
    title: Testing accessibility quality gates
    files: ['tests\hitl\test_accessibility_templates.py']
    depends_on: [T-006, T-012, T-015]
  - id: T-017
    slice: SL-006
    title: Emitting metadata-only observability
    files: ['src\living_adr\hitl\observability.py', 'src\living_adr\apps\workflow_service\hitl_routes.py', 'tests\hitl\test_boundary.py']
    depends_on: [T-008, T-009, T-012, T-013]
  - id: T-018
    slice: SL-006
    title: Enforcing capability and mutation boundary
    files: ['tests\hitl\test_boundary.py']
    depends_on: [T-017]
```

## Validation Plan
- Run the existing project test command after implementation, expected `uv run pytest` if scaffolded.
- Run existing lint/format command if present, expected `uv run ruff check`.
- Add no new tooling beyond project choices.
- Boundary tests must fail if UI code imports graph store, approval mutation service, Claude adapter, or GitHub provider.

## Sequencing Notes
SL-001 must land first because all route/template work depends on stable view models and gateway mapping. SL-006 lands last because it hardens behavior across the completed UI surface.
