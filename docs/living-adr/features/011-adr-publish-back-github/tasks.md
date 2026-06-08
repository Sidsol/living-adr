# Tasks: adr-publish-back-github

## Story: Publication policy and target resolution (S011-01)

- [x] **T011-S1-001 — Defining publication request and target models**  
  Create DTOs for approved ADR publication request, target branch/path template, content hash, result status, and target fingerprint.
- [x] **T011-S1-002 — Resolving publication policy and target branch**  
  Read `RepositoryConfig.adr_publication_policy`, target branch, and default `docs\adr\NNNN-<slug>.md` behavior without hardcoding repository assumptions.
- [x] **T011-S1-003 — Computing publication fingerprints**  
  Build deterministic fingerprints from repository, ADR record id, approved content hash, target policy, branch, path template, and `decision_id`.

## Story: Approval-bound publication audit and idempotency (S011-02)

- [x] **T011-S2-001 — Creating publication repository records**  
  Add durable publication intent/result records keyed by `decision_id` and repository.
- [x] **T011-S2-002 — Reserving publication intent by decision**  
  Reserve a publication attempt before remote writes and persist skipped/error/success statuses.
- [x] **T011-S2-003 — Enforcing ApprovalBoundMutationService validation**  
  Require feature 010 approval validation/consumption before any SCM provider write.
- [x] **T011-S2-004 — Returning idempotent prior publication results**  
  Return prior success/skip for same `decision_id` and same fingerprint; reject mismatched retries.

## Story: ADR slugging, numbering, and path allocation (S011-03)

- [x] **T011-S3-001 — Implementing deterministic ADR slugging**  
  Convert ADR titles to lowercase hyphenated slugs with ASCII fallback and length cap.
- [x] **T011-S3-002 — Parsing existing ADR numeric prefixes**  
  Read configured directory listings and parse valid numeric filename prefixes while ignoring malformed files.
- [x] **T011-S3-003 — Allocating next ADR path**  
  Choose max existing prefix + 1, defaulting to `0001`, and render the configured path template.
- [x] **T011-S3-004 — Detecting same-decision existing files**  
  Identify already-published ADRs by `livingadr_decision_id` marker to support recovery and retry.

## Story: GitHub provider contents commit through SCM port (S011-04)

- [x] **T011-S4-001 — Extending SCM contents port**  
  Add provider-neutral repository file listing/read/write operations if absent from feature 003 contracts.
- [x] **T011-S4-002 — Implementing GitHub file listing and read checks**  
  Implement target-branch directory listing and file existence checks in `GitHubProvider` behind the port.
- [x] **T011-S4-003 — Committing ADR file through GitHub provider**  
  Commit approved ADR Markdown with decision-linked commit metadata and return commit SHA/path.
- [x] **T011-S4-004 — Handling commit conflicts and provider errors**  
  Refresh listing/head on conflicts, retry up to three times, and dead-letter structured failures.

## Story: Workflow handoff, boundary tests, and observability (S011-05)

- [x] **T011-S5-001 — Wiring workflow publication node**  
  Connect approved ADR handoff from feature 015/010 into publication service without owning approval minting.
- [x] **T011-S5-002 — Emitting publication audit and observability**  
  Record metadata-only publication events linked by `decision_id`; avoid raw ADR/diff/prompt export by default.
- [x] **T011-S5-003 — Adding read-side boundary tests**  
  Prove MCP/read-side modules cannot import or call publication write paths.
- [x] **T011-S5-004 — Verifying end-to-end publish-back contract**  
  Test approved ADR to policy resolution, approval validation, path allocation, provider commit, and audit linkage.

## Counts

```yaml
feature_id: "011"
slice_count: 5
task_count: 19
slices:
  S011-01: 3
  S011-02: 4
  S011-03: 4
  S011-04: 4
  S011-05: 4
```

