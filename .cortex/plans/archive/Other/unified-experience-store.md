---
title: "Unified Experience Store in SQLite"
component: "memory"
work_type: "feature"
status: DONE
priority: "High"
created: "2026-07-19"
depends_on: []
---

## Goal

Create a single SQLite-backed experience store (`experience.db` or an extension of `temporal.db`) with the Trellis-style schema — `tasks`, `sessions`, and `nodes(id, parent_id, session_id, artifact_ref, fitness, status, step_number)` — and instrument the existing pipeline phases to write nodes with quality-gate results as fitness scores.

## Context

The Experience Graphs paper (arXiv:2606.29823, Trellis/Meta) shows that persisting an agent's full search history as versioned, queryable database state enables crash recovery, cross-session reuse, and query-based learning. Cortex already has the raw ingredients — WAL (`.cortex/wal/write_log.jsonl`), `temporal.db` (SPO triples), `pipeline_handoff` (per-phase JSON files), and `run_quality_gate()` results — but they are disconnected silos: fitness signals are consumed once and discarded, handoff state is cleared per-session, and no lineage links attempts to outcomes. A unified store is the foundation for pipeline resume, vector-seeded recall, and query-based analysis (separate dependent plans).

## Scope

**in_scope**

- SQLite schema: `tasks` (spec + success metric), `sessions` (algorithm, progress, owner), `nodes` (parent link, artifact reference, fitness, status, step_number), with migrations.
- Async storage layer (Pydantic 2 models, typed repository API) following the existing `temporal.db` access patterns.
- Instrumentation hooks: pipeline phases (`commit-phase-a`, `fix-quality` iterations, `implement-code` subtasks) write one node per attempt via `pipeline_handoff` integration.
- Each `run_quality_gate()` result recorded as the fitness of the node that produced it.
- Large artifacts (gate logs, diffs) stored on disk under `.cortex/`, linked by reference from `nodes.artifact_ref`.

**out_of_scope**

- Pipeline resume/frontier queries (separate plan: pipeline-resume-frontier-query).
- Embeddings or vector retrieval (separate plan: vector-seeded-experience-recall).
- Rewiring `/cortex/analyze` (separate plan: analyze-experience-graph-queries).
- Content-preserving WAL deltas (separate plan: content-preserving-wal-as-of).
- Any distributed/serverless engine (axiom/Velox explicitly rejected — SQLite is the right scale).

## Approach

Extend the existing storage subsystem with an experience-store module: define Pydantic 2 models mirroring the four-level Trellis hierarchy (task → session → node → prompt/artifact reference), an async repository over `aiosqlite` (matching current `temporal.db` conventions), and a thin recording API (`record_node`, `set_fitness`, `link_artifact`). Wire recording calls into `pipeline_handoff` phase transitions and the quality-gate result path so experience accumulates as a side effect of normal pipeline execution, with no behavior change when recording fails (best-effort, logged).

## Implementation Steps

1. Define Pydantic 2 models: `ExperienceTask`, `ExperienceSession`, `ExperienceNode` (fields: `id`, `parent_id`, `session_id`, `artifact_ref`, `fitness`, `status`, `step_number`).
2. Create SQLite schema migration and `ExperienceStore` async repository (create/read/append operations; no deletes).
3. Add artifact-reference helper: persist large payloads (gate logs, diffs) to `.cortex/experience/artifacts/` and store the relative path in `artifact_ref`.
4. Integrate with `pipeline_handoff`: on phase start/complete/fail, record a node with parent lineage and `step_number`.
5. Integrate with `run_quality_gate()` result handling: attach gate outcome (pass/fail + score summary) as node fitness.
6. Add configuration flag to enable/disable experience recording (default enabled) and ensure failures never break the pipeline.
7. Unit and integration tests for schema, repository, and both instrumentation paths.
8. Update memory bank (`systemPatterns.md`, `techContext.md`) documenting the experience-store architecture.

## Verification Checklist

- Step 1–2: search for existing `temporal.db` access patterns (`rg "aiosqlite" src/`) and mirror them; re-read the new models/repository files after changes.
- Step 4: search `rg "pipeline_handoff" src/` for all phase-transition call sites; confirm each records a node; re-read handoff module after edits.
- Step 5: search `rg "run_quality_gate" src/` for result-handling sites; confirm fitness attachment; re-read gate result module.
- Step 6: verify a forced storage failure (locked DB) leaves the pipeline functional (integration test).
- Step 7: `run_quality_gate()` passes with new tests included.

## Dependencies

- None (foundation plan). Downstream plans depend on this one.

## Success Criteria

- `experience.db` exists with `tasks`, `sessions`, `nodes` tables and passes migration tests.
- A full `/cortex/fix` or `/cortex/commit` run produces ≥1 task row, ≥1 session row, and one node per phase/iteration with correct parent lineage.
- Every quality-gate invocation during a pipeline run is recorded as fitness on exactly one node.
- Recording failures are logged and never abort a pipeline (verified by test).
- Quality gate green; coverage for new modules ≥95%.

## Testing Strategy

- Unit tests (AAA): model validation, repository CRUD, artifact-ref round-trip, migration idempotency.
- Integration tests: simulated pipeline phase sequence writes correct node lineage; gate-result → fitness attachment; disabled-flag and storage-failure paths.
- Negative cases: malformed artifact refs, missing parent nodes, concurrent session writes.
- Target: ≥95% coverage on new experience-store modules.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Recording overhead slows pipelines | Best-effort async writes; single transaction per node; benchmark in tests |
| Schema churn once downstream plans land | Version schema with migrations from day one; keep node payload minimal, artifacts by reference |
| DB lock contention with concurrent sessions | WAL journal mode; short transactions; retry-with-backoff in repository |
| Silent recording failures hide data loss | Log at WARNING with trace id; health counter surfaced via `session()` |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
