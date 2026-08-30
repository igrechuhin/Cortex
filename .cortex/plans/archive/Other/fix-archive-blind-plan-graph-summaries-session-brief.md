---
title: "Fix archive-blind plan-graph summaries in session brief and optimization handlers"
component: "plans"
work_type: fix
status: PENDING
priority: Medium
execution: agent
created: 2026-08-30
depends_on: []
---

## Goal

Make every plan-graph summary surface reflect true completion state for archived dependencies, so `session()` and the optimization handlers stop reporting plans as BLOCKED by dependencies that are already archived with `status: DONE`.

## Context

Discovered 2026-08-30 during a `/cortex/do` loop run. `session()` reported `"0 plans READY, 1 plans BLOCKED by 2 outstanding dependency link(s)"` for `content-preserving-wal-as-of`, while `plan(operation="graph")` — called moments later in the same session — correctly listed that same plan under `ready` with both dependencies (`unified-experience-store`, `analyze-experience-graph-queries`) under `done`. The orchestrator had to manually override the session brief to select the work at all.

The archived plan `fix-plan-graph-archive-blindness-masking-satisfied-dependencies.md` fixed exactly this defect, but only for one call site: `src/cortex/tools/plans/plan.py:468` now passes `include_archive=True`. Its own Scope flagged an unaudited sibling ("Audit `roadmap_plan_graph_annotate.py` ... for the same defect"), and that audit was never completed. Two call sites remain archive-blind:

- `src/cortex/tools/session/brief_loaders.py:162` — `compute_artifact_graph(plans_dir, include_archive=False, max_ascii_edges=10)`
- `src/cortex/tools/optimization/handlers_format.py:219` — same call, same hardcoded `False`

Root cause is that `include_archive` is a per-caller decision with an unsafe default rather than a single shared one. `_apply_blocked_by` treats `dep not in nodes` as unsatisfied, so any archived dependency is silently read as outstanding.

## Scope

**in_scope**

- Flip both remaining summary call sites to `include_archive=True`.
- Prefer a single shared default over patching each caller, so a future third call site cannot reintroduce the defect — this is the root-cause fix, not a symptom fix.
- Regression test asserting a session-brief plan-graph summary reports a plan with an archived `status: DONE` dependency as READY, not BLOCKED.

**out_of_scope**

- `list_plan_slug_paths(plans_dir, include_archive=False)` in `register_artifact_graph.py:197` — that one is deliberate (it enumerates active plans to update, not dependency nodes). Do not change it.
- `operation="list"`'s `include_archive` wire field, which correctly defaults to `False`.
- Retroactively normalizing `status: COMPLETE` frontmatter on other archived plans (still a separate cleanup; `PlanStatus` only recognizes `DONE`).

## Approach

Grep every `compute_artifact_graph` call site. Where the call builds a *dependency-resolution* view, archive inclusion must be on. Rather than editing three literals, give the graph-summary path one helper (or default `include_archive=True` on `compute_artifact_graph`, inverting the flag for the one deliberate `list` caller) so the safe behavior is the default and the exception is explicit.

## Success Criteria

- `session()`'s `plan_graph_summary` and `plan(operation="graph")` agree on READY/BLOCKED for the same plan set.
- A plan whose only dependencies are archived with `status: DONE` appears READY in the session brief.
- Regression test added and passing; `run_quality_gate()` green.

## Testing Strategy

- Unit test with a fixture archived dependency plan at `status: DONE` plus a dependent plan in the active `.cortex/plans/` root; assert the session-brief summary counts it READY and reports zero outstanding dependency links.
- Assert the deliberate `register_artifact_graph.py` `include_archive=False` call is unchanged, so the fix cannot silently widen.

## Change History

*No revisions recorded yet.*
