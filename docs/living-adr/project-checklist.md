# CRISPY Project Checklist: LivingADR

| Field | Value |
|---|---|
| Project | LivingADR |
| Folder | `C:\repos\crispy-docs\projects\004-living-adr` |
| Created | 2026-05-29 |
| Yield status | ✅ Ready for feature-level hand-off |
| Blocker count | 0 |

## Artifact Presence and Consistency

- ✅ vision.md exists and is non-empty
- ✅ domain-research.md exists and is non-empty
- ✅ architecture.md exists and is non-empty
- ✅ scaffold-report.md exists and is non-empty
- ✅ feature-map.md exists and is non-empty
- ✅ roadmap.md exists and is non-empty
- ✅ review-gates.yaml exists and is non-empty
- ✅ Feature map contains exactly 15 features with IDs 001-015
- ✅ Feature-map dependency graph matches authoritative edges
- ✅ Roadmap milestones cover same 15-feature set as feature-map
- ✅ Roadmap waves match dependency graph fan-out
- ✅ Dependency graph is acyclic
- ✅ Feature folders exist for 001-015 including 015-workflow-orchestration-checkpointing
- ✅ review-gates.yaml gate architecture=passed
- ✅ review-gates.yaml gate feature_map=passed
- ✅ review-gates.yaml gate roadmap=passed
- ✅ Vision themes TH-01..TH-07 each map to at least one feature

## Project Review Gates

- ✅ `architecture`: `passed`
- ✅ `feature_map`: `passed`
- ✅ `roadmap`: `passed`

## DAG Integrity

- ✅ Authoritative dependency graph is acyclic and matches features 001-015.
- ✅ Critical path length confirmed by roadmap: 7 feature nodes.
- ✅ Sequential feature-level run order: 001, 002, 003, 006, 013, 004, 005, 014, 007, 015, 012, 008, 009, 010, 011.

## Theme Coverage

- ✅ `TH-01` → 001, 003
- ✅ `TH-02` → 004, 005
- ✅ `TH-03` → 015, 008, 009, 010
- ✅ `TH-04` → 006, 007, 011
- ✅ `TH-05` → 012
- ✅ `TH-06` → 013
- ✅ `TH-07` → 002, 014

## Walking Skeleton and MVP Cut

- ✅ Walking skeleton: `001` (`walking-skeleton-smoke`).
- ✅ MVP cut line: `M4` — First End-to-End ADR and MCP Context Delivery.
- ⚠️ Post-MVP hardening remains in `M5`: `013`, `014`.

## Carried-Forward Open Questions / Risk Notes

- ⚠️ ** exact GitHub App permissions and local webhook delivery path
- ⚠️ held-out query/evaluation rubric for SM-03/SM-04
- ⚠️ confidence thresholds per classifier
- ⚠️ direct commit vs PR publish-back policy
- ⚠️ and post-PoC MCP HTTP/auth and SQLite migration triggers
- ⚠️ Architecture: What exact GitHub App webhook events and non-contents permissions should be requested for PoC while preserving least privilege?
- ⚠️ Architecture: How will local PoC webhook delivery be exposed: user-provided tunnel, internal relay, manual replay fixture, or a small hosted PoC endpoint?
- ⚠️ Architecture: Which specific personal GitHub repo will be configured at startup, and does it contain or can it generate enough dependency/schema/API-contract changes to validate SM-01 and SM-02?
- ⚠️ Architecture: What held-out query set and human scoring rubric define SM-03 retrieval relevance and SM-04 architecture question coverage?
- ⚠️ Architecture: What confidence threshold and evidence bundle should distinguish "no ADR needed" from "draft ADR for review" for each structural-change class?
- ⚠️ Architecture: What exact source-of-truth hierarchy applies when code, PR text, approved ADRs, graph projections, and model-inferred facts conflict?
- ⚠️ Architecture: What temporal model is required for superseded ADRs, PRs, commits, releases, and graph snapshots before multi-repo rollout?
- ⚠️ Architecture: For publish modes, should GitHub ADR publication use direct commits or open PRs for approved ADR markdown?
- ⚠️ Architecture: Which post-PoC deployment topology change triggers the SQLite→snapshot/Postgres migration — split-host, multi-tenant, or scale-out?
- ⚠️ Architecture: Does Anthropic ZDR or equivalent contractual term apply to the post-PoC tenant?
- ⚠️ Architecture: Should `living-adr.config.yaml` support templating / environment-variable interpolation for installation ids and per-repo overrides, or remain literal-only? (Post-PoC ergonomics question.)
- ⚠️ Architecture: What future HTTP MCP auth model is acceptable if the read-only context server moves from local stdio to remote/shared deployment?
- ⚠️ Architecture: What normalized SCM event vocabulary is sufficient for Azure DevOps service hooks without leaking GitHub-only assumptions into workflow nodes?

## Issues Found

- ✅ No blockers found.
