---
title: "Artifact Graph for Plan Dependencies"
component: planning
work_type: feature
status: PENDING
priority: medium
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
