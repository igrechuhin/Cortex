---
title: "Pipeline Resume as a Frontier Query"
component: "pipeline"
work_type: "feature"
status: PENDING
priority: "High"
created: "2026-07-19"
depends_on: []
---

## Goal

Make interrupted `/cortex/commit` and `/cortex/fix` pipeline runs resumable by querying the experience store for the last committed node of a session and continuing from it, instead of restarting from scratch or manually reading handoff files.

## Context

The Experience Graphs paper (arXiv:2606.29823) demonstrates that when all search state lives in the database, recovery becomes a query, not a checkpoint: a dead worker loses at most one step, and any worker resumes from the last committed node. Cortex's `pipeline_handoff` already has snapshot/rollback/mark_running operations — halfway to this model — but a crashed pipeline currently restarts from scratch. With nodes and status recorded in the experience store (see plan `unified-experience-store`), resume becomes "select the last committed node for this session and continue."

## Scope

**in_scope**

- Frontier query API on the experience store: latest committed node + status for a given session/pipeline run.
- Resume path in the pipeline orchestrator flow: on start, detect an incomplete prior run for the same goal and offer/perform continuation from the frontier node.
- Mapping between experience-store node status and existing `pipeline_handoff` phase states (snapshot/rollback/mark_running).
- Stale-run handling: expiry rules for abandoned runs so resume prompts are not offered indefinitely.
- Surfacing incomplete pipelines in `session()` output using frontier data.

**out_of_scope**

- The experience-store schema itself (plan: unified-experience-store).
- Multi-worker/distributed execution — single-machine resume only.
- Vector retrieval or analyze rewiring (separate plans).

## Approach

Build a `frontier(session_id)` query on the `ExperienceStore` repository returning the deepest committed node with its phase context. Extend `pipeline_handoff` so phase state transitions and node status stay consistent (one source of truth: the store; handoff files become a projection or are validated against it). On pipeline start, check for incomplete runs matching the current goal; if found and fresh, reconstruct phase position from the frontier node and skip completed phases.

## Implementation Steps

1. Add `frontier` and `incomplete_runs` query methods to the experience-store repository (typed Pydantic results).
2. Define node status lifecycle (`pending` → `running` → `committed` | `failed`) and enforce transitions in the recording API.
3. Reconcile `pipeline_handoff` phase state with node status: write both atomically or derive handoff view from the store.
4. Add resume detection to pipeline start: query incomplete runs for the same goal; expose result in `session()` `incomplete_pipelines`.
5. Implement continuation: reconstruct completed-phase list from frontier lineage, skip them, resume at the next phase.
6. Add staleness policy (e.g., runs older than a configurable TTL are marked abandoned, not offered for resume).
7. Tests: crash-simulation integration tests (kill after each phase, resume, verify no repeated phases and no lost state).
8. Update Synapse commit/fix prompt docs and memory bank to describe resume behavior.

## Verification Checklist

- Step 3: search `rg "snapshot|rollback|mark_running" src/` for all handoff state call sites; confirm each maps to a node-status transition; re-read handoff module after edits.
- Step 4: confirm `session()` output schema change is reflected in its tests (`rg "incomplete_pipelines" src/ tests/`).
- Step 5: after implementation, re-read orchestrator flow end-to-end to confirm no phase can run twice.
- Step 7: run the full test suite via `run_quality_gate()`.

## Dependencies

- Plan: `unified-experience-store` — COMPLETE (archived at `.cortex/plans/archive/Other/unified-experience-store.md`).

## Success Criteria

- Killing a pipeline after any phase and restarting resumes at the next phase (verified by integration tests for every phase boundary).
- No phase executes twice on resume; no completed work is lost.
- `session()` lists incomplete pipelines with their frontier phase.
- Stale runs past TTL are never offered for resume.
- Quality gate green; ≥95% coverage on new resume modules.

## Testing Strategy

- Unit tests (AAA): frontier query correctness, status transition enforcement, staleness policy.
- Integration tests: simulated crash at each phase boundary followed by resume; handoff/store consistency checks; TTL expiry.
- Negative cases: corrupted node lineage, frontier on empty store, concurrent resume attempts.
- Target: ≥95% coverage on new modules.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Handoff files and store drift out of sync | Single-writer recording API; consistency check on resume that prefers the store |
| Resuming a run whose working tree changed underneath | Validate git status/rollback snapshot hash before resuming; fall back to fresh start on mismatch |
| Resume masks a genuinely failed phase | Only `committed` nodes are resumable; `failed` frontier forces the fix path |
| Complexity creep in orchestrator prompts | Keep resume logic in MCP tools; prompts only read `incomplete_pipelines` |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
