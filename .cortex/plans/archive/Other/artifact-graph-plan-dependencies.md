---
title: "Artifact Graph for Plan Dependencies"
component: planning
work_type: feature
status: PENDING
priority: Medium
created: 2026-04-06
depends_on: []
---

## Goal

Add explicit dependency declarations to plan YAML frontmatter (`depends_on: [plan-id-1, plan-id-2]`). The `plan` tool computes a real-time dependency graph: a plan is BLOCKED if its dependencies are not completed, READY if they are. Roadmap views surface this graph, making blockers explicit rather than implicit.

## Context

Inspired by OpenSpec's filesystem-as-database artifact graph with dynamic dependency resolution. Currently, Cortex plans have a `depends_on` field but it is not enforced or visualized. There is no mechanism to compute reachable plans, detect cycles, or surface "what is ready to implement now." The roadmap is a flat list; blocked plans are invisible until implementation fails.

## Implementation Steps

### Step 1: Formalize `depends_on` and plan status model

- Update `PlanMetadata` (or equivalent) in `src/cortex/core/models.py`:
  - `depends_on: list[str]` — list of plan slugs (filename without `.md`).
  - `status: Literal["PENDING", "IN_PROGRESS", "BLOCKED", "DONE", "READY"]`
  - `blocked_by: list[str]` — computed at read time, not stored.
- Define `PlanStatus` enum instead of bare `Literal` for type safety.

**Verification**: Model defined, `PlanStatus` enum importable.

### Step 2: Add artifact graph computation

- Add `compute_artifact_graph(plans_dir: Path) -> ArtifactGraph` in `src/cortex/core/artifact_graph.py` (new file).
- `ArtifactGraph` model:
  - `nodes: dict[str, PlanNode]` keyed by slug
  - `edges: list[tuple[str, str]]` (dependent → dependency)
  - `ready: list[str]` — plans with all dependencies DONE
  - `blocked: list[str]` — plans with at least one dependency not DONE
  - `cycles: list[list[str]]` — detected dependency cycles
- Use Kahn's algorithm for topological sort; detect cycles during sort.

**Verification**: Graph computation correctly identifies READY, BLOCKED, and cyclic plans.

### Step 3: Compute graph on `plan(operation="register")`

- After writing the plan file, compute the artifact graph.
- If the new plan's `depends_on` references non-existent plans, log a warning but proceed.
- If the new plan creates a cycle, reject registration with a clear error.
- Set plan status to `BLOCKED` if any dependency is not DONE; `PENDING` otherwise.

**Verification**: Registering a plan with unsatisfied dependencies sets status to BLOCKED; cyclic dependency rejected.

### Step 4: Add `plan(operation="graph")`

- Returns the full artifact graph as structured data:
  - `ready: list[str]` — slugs of immediately implementable plans
  - `blocked: list[str, list[str]]` — slug → list of blocking dependency slugs
  - `in_progress: list[str]`
  - `done: list[str]`
  - `cycles: list[list[str]]` — should always be empty post-validation
- Also returns a text-based ASCII DAG for display in `session()`.

**Verification**: `plan(operation="graph")` returns correct status for a set of interdependent plans.

### Step 5: Update `plan(operation="complete")` to trigger graph recomputation

- When a plan is marked DONE, recompute the graph.
- Any previously BLOCKED plans whose dependencies are now all DONE → transition to READY.
- Write updated statuses back to plan frontmatter.
- Report how many plans were unblocked.

**Verification**: Completing a dependency plan unblocks dependent plans and updates their status.

### Step 6: Surface graph in `session()` and roadmap

- In `session()` startup, include the graph summary: "N plans READY, M plans BLOCKED by X dependencies."
- Include the ASCII DAG in `session()` output (truncated to top 10 nodes if large).
- In `manage_file(operation="read", file_name="roadmap.md")`, annotate BLOCKED entries with their blocking dependencies.

**Verification**: Session output includes graph summary; roadmap read output annotates BLOCKED plans.

### Step 7: Add graph visualization to `cortex://context` resource

- Include the ready/blocked lists in context so agents immediately know what is safe to implement next.

**Verification**: Context resource includes graph summary.

### Step 8: Tests

- Unit: `compute_artifact_graph` — all plans independent (all READY); linear chain (only first READY); diamond dependency; cycle detection.
- Unit: Registration status assignment.
- Unit: `plan(operation="complete")` unblocking cascade.
- Unit: ASCII DAG rendering.
- Integration: Multi-plan scenario — register → complete → verify unblocking.

**Verification**: All tests pass, ≥ 95% coverage on new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `PlanStatus`, updated `PlanMetadata` | `src/cortex/core/models.py` | full file |
| 2 | `ArtifactGraph`, `compute_artifact_graph` | `src/cortex/core/artifact_graph.py` | full file |
| 3 | Graph computation in `register` | `src/cortex/tools/plan.py` | `register` branch |
| 4 | `plan(operation="graph")` | `src/cortex/tools/plan.py` | `graph` branch |
| 5 | Unblocking in `complete` | `src/cortex/tools/plan.py` | `complete` branch |
| 6 | Graph in session output | `src/cortex/tools/session.py` | startup logic |
| 7 | Graph in context resource | `src/cortex/resources/context.py` | full file |
| 8 | Test files | `tests/` | new test files |

## Dependencies

- Existing `plan` tool (all operations)
- Existing `session()` tool
- Existing `cortex://context` resource
- `PlanStatus` enum (Step 1)
- `artifact_graph.py` (Step 2)

## Success Criteria

- `depends_on` is enforced: plans with unsatisfied dependencies register as BLOCKED.
- Cyclic dependencies are rejected at registration time.
- Completing a plan automatically unblocks dependent plans.
- `session()` and roadmap surface the dependency graph.
- No `Any` types; functions ≤ 30 lines; ≥ 95% coverage.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Graph algorithm correctness (Kahn's); cycle detection; ASCII DAG renderer.
- **Integration**: Register → complete → unblock cascade with real temp plan files.
- **Edge cases**: Single plan (trivially READY); plan depending on itself (cycle); `depends_on` referencing a plan that doesn't exist yet (warning, not error).

## Partial Progress Log

- 2026-04-11: Steps 1–2 — Added `PlanStatus` enum; `PlanNode` / `ArtifactGraph` / `compute_artifact_graph` (Tarjan SCC cycle detection); extended unit tests — files: src/cortex/core/models/_enums.py, src/cortex/core/models/**init**.py, src/cortex/core/artifact_graph.py, tests/unit/test_artifact_graph.py
- 2026-04-11: Step 3 — `plan(operation="register")` now validates dependency cycles (reject), warns on missing `depends_on` slugs, syncs plan frontmatter `status` to BLOCKED/PENDING after roadmap write — files: src/cortex/core/artifact_graph.py, src/cortex/tools/plans/register.py, src/cortex/tools/plans/register_artifact_graph.py, tests/unit/test_artifact_graph.py, tests/tools/test_plan_operations.py
- 2026-04-11: Step 4 — `plan(operation="graph")` returns ready, blocked (slug → blockers), in_progress, done, cycles, and ASCII edge list; implementation in `plan_graph.py` — files: src/cortex/tools/plans/plan_graph.py, src/cortex/tools/plans/plan.py, tests/tools/test_plan_tool_dispatch.py
- 2026-04-11: Step 5 — `plan(operation="complete")` runs post-success dependency resync (`include_archive` graph, frontmatter updates, `plans_unblocked` count) — files: src/cortex/core/artifact_graph.py, src/cortex/tools/plans/register_artifact_graph.py, src/cortex/tools/plans/completion.py, src/cortex/tools/plans/completion_models.py, src/cortex/tools/plans/completion_ops.py, src/cortex/tools/plans/plan.py, tests/unit/test_artifact_graph.py, tests/tools/test_plan_completion.py
- 2026-04-11: Steps 6–7 — Session brief gains `plan_graph_summary` / `plan_graph_ascii_edges`; `manage_file` roadmap reads append BLOCKED hints; `cortex://context` JSON gains `plan_graph_*` via `inject_plan_graph_into_context_result`; shared `build_plan_graph_surface_bundle` / `render_plan_dependency_edges_ascii` — files: src/cortex/tools/session/models.py, src/cortex/tools/session/start_models.py, src/cortex/tools/session/brief_helpers.py, src/cortex/tools/session/brief.py, src/cortex/tools/plans/plan_graph.py, src/cortex/tools/plans/roadmap_plan_graph_annotate.py, src/cortex/tools/files/crud_flow.py, src/cortex/tools/optimization/handlers_format.py, tests/tools/test_roadmap_plan_graph_annotate.py
