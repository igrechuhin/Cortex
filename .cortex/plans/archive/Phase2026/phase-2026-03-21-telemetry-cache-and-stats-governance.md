---
title: "Telemetry — Synapse usage cache policy and context-usage-statistics semantics"
component: telemetry
work_type: governance
status: PENDING
priority: P2
created: 2026-03-21
depends_on: []
sources:
  - .cortex/reviews/code-review-report-2026-03-21T11-18.md
  - docs/architecture/tool-usage-tracking.md
---

## Goal

Remove ambiguity about **what belongs in git** under `.cortex/synapse/.cache/usage/` and how **`.cortex/.session/context-usage-statistics.json`** aggregates should be interpreted (cumulative vs windowed, reset behavior).

## Context

- Code review (2026-03-21): large diffs from daily usage JSON; risk of merge noise and unclear whether caches are source-of-truth in the superproject/submodule.
- Aggregate fields can shift sharply when rollups or classification change — operators may misread trends as regressions.

## Implementation steps

1. **Version-control policy** — Document whether `usage/events/*.json` is committed, gitignored, or generated in CI; align with Synapse submodule workflow and commit pipeline guidance.
2. **Schema / semantics doc** — Extend `docs/architecture/tool-usage-tracking.md` (or session telemetry doc) with: fields in `context-usage-statistics.json`, when `last_updated` changes, whether counts are lifetime or windowed, and what triggers backfill/reconcile (reference `reconcile_context_usage_statistics_entries` if present).
3. **Optional inline schema** — Add a top-level `"schema_version"` or comment block in JSON if format allows (JSON: no comments — use adjacent `README` in `.cortex/.session/` or doc-only).
4. **PR hygiene** — If caches stay tracked: add reviewer checklist bullet (“confirm intentional analytics rollup”); if not: update `.gitignore` and migration note for existing clones.

## Verification checklist (per step)

| Step | What to search for | Scope | Re-read |
|------|---------------------|--------|---------|
| 1 | `.cache/usage`, gitignore | `.gitignore`, `.cortex/synapse/` | submodule README |
| 2 | context-usage-statistics | `docs/architecture/` | code that writes stats |
| 4 | contributor | `AGENTS.md` or `docs/guides/` | single source |

## Dependencies

- Coordination with Synapse maintainers if ignore rules live in submodule.

## Success criteria

- Written policy answers: “Should I commit today’s `2026-03-21.json`?” in one paragraph.
- Stats JSON semantics documented so support can explain sudden drops in `total_load_context_calls` without code archaeology.

## Testing strategy (95%+ coverage target for new code)

- If only docs: link-check or existing docs gate.
- If adding `schema_version`: unit test that loader accepts missing (default) and current version.
