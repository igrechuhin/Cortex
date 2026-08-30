---
title: "Fix plan(graph) archive-blindness masking satisfied dependencies"
component: "plans"
work_type: fix
status: PENDING
priority: Medium
created: 2026-07-20
depends_on: []
status: PENDING
---

## Goal

`plan(operation="graph")` permanently reports downstream plans as BLOCKED by a dependency once that dependency plan file is archived, even when the archived dependency's frontmatter `status: DONE` — because the public tool always calls `plan_graph_json(ctx, include_archive=False)` with no way for callers to pass `include_archive=True` (the `include_archive` field exists on the internal Pydantic request model but is not exposed as a parameter on the `plan` MCP tool signature).

## Context

Discovered 2026-07-20 while running `/cortex/do` on plan `synapse-rule-provenance`: `plan(operation="graph")` reported it BLOCKED by `analyze-experience-graph-queries` and `unified-experience-store`, both of which are fully implemented and recorded COMPLETE in `activeContext.md` (2026-07-19/2026-07-20) but physically live under `.cortex/plans/archive/Other/` (archived before their frontmatter `status` was ever set to `DONE` — a separate bookkeeping gap, since fixed for these two plans in this session by setting `status: DONE` in their frontmatter). Even after that fix, `plan(operation="graph")` still reports `synapse-rule-provenance` as blocked, because `_load_raw_nodes_and_edges` (`src/cortex/core/artifact_graph.py`) only scans `.cortex/plans/*.md` when `include_archive=False`, so archived dependency slugs are simply absent from the node set — `_apply_blocked_by` then treats `dep not in nodes` as an unsatisfied dependency regardless of true completion state. Contrast with `sync_plan_dependency_statuses_after_completion` (`src/cortex/tools/plans/register_artifact_graph.py`), which correctly calls `compute_artifact_graph(plans_dir, include_archive=True)` — so the completion-sync path is archive-aware but the read-only `graph` query path is not.

## Scope

**in_scope**

- Expose `include_archive` (default `True`, since most completed dependencies live in the archive) as a parameter on the `plan` MCP tool for `operation="graph"`, or change `plan_graph_json`'s default call site in `plan.py` to pass `include_archive=True` unconditionally for the `graph` operation.
- Regression test: a plan whose dependency is archived with `status: DONE` must appear in `ready`, not `blocked`.
- Audit `roadmap_plan_graph_annotate.py` (currently hardcodes `include_archive=False`) for the same defect in roadmap rendering.

**out_of_scope**

- Any change to plan authoring/completion workflows.
- Retroactively fixing `status:` frontmatter on other archived plans (separate cleanup; many archived plans use `status: COMPLETE`, a non-canonical value the parser silently treats as `PENDING` — `PlanStatus` enum only recognizes `DONE`).

## Approach

Change the `graph` operation's call site (`src/cortex/tools/plans/plan.py`, `_handle_special_plan_operations`) to pass `include_archive=True`, or add an explicit tool parameter with that default. Add a unit test constructing an archived dependency plan with `status: DONE` and asserting the dependent plan is `ready`.

## Success Criteria

- `plan(operation="graph")` reflects true completion state for archived dependencies.
- Regression test added and passing.

## Testing Strategy

- Unit test in `tests/core/test_artifact_graph.py` (or equivalent) with a fixture archived plan at `status: DONE` and a dependent plan in the active `.cortex/plans/` root; assert dependent is in `ready`.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
