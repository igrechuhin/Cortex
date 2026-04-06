---
title: "Parallel Task Markers [P]"
component: planning
work_type: feature
status: PENDING
priority: medium
created: 2026-04-06
depends_on: []
---

## Goal

Add `[P]` markers to implementation steps that have no data dependency and can run concurrently. The orchestrator uses these markers to spawn multiple `implement-code` subagents in isolated git worktrees, enabling genuine parallelism instead of sequential execution.

## Context

Inspired by GitHub Spec Kit's parallel task markers and its MAQA multi-agent orchestration extension. Currently, `implement-code` receives a flat task list and executes steps sequentially. Many steps are independent (e.g., writing tests for module A while implementing module B). Explicit parallelism hints allow the `/cortex/do` orchestrator to exploit this safely.

## Implementation Steps

### Step 1: Define marker format and dependency model

- Standard marker: `[P]` prefix on an implementation step heading — e.g., `### [P] Step 3: Add unit tests`.
- Dependency declaration: `[P:after=2,3]` — step is parallel but depends on steps 2 and 3 completing first.
- Add `TaskNode` Pydantic model in `src/cortex/core/models.py`:
  - `step_id: int`
  - `title: str`
  - `parallel: bool`
  - `depends_on: list[int]`
  - `content: str`

**Verification**: Model defined, format documented.

### Step 2: Add task graph parser

- Add `parse_task_graph(plan_content: str) -> list[TaskNode]` in `src/cortex/core/plan_utils.py`.
- Parse all `### Step N:` headings, detect `[P]` and `[P:after=...]` markers.
- Build adjacency list: edges from dependency declarations.
- Validate: no cycles (raise `PlanValidationError` if cycle detected); no references to non-existent steps.

**Verification**: Parser correctly identifies parallel vs. sequential steps; cycle detection raises error.

### Step 3: Add `[P]` emission to plan creation

- In `plan(operation="create")`, when `think()` analysis determines steps are independent, prefix their headings with `[P]`.
- Heuristic for independence: steps that operate on different files/modules with no shared output.
- Never mark steps as `[P]` if they depend on a previous step's output.
- Use `think()` to reason about step dependencies before marking.

**Verification**: Created plan with clearly independent steps has `[P]` markers; dependent steps do not.

### Step 4: Add dependency validation to `plan(operation="register")`

- Before registering, call `parse_task_graph()`.
- If a cycle is detected, reject registration and return a clear error.
- Include `parallel_steps_count` and `sequential_steps_count` in the registration response.

**Verification**: Plan with cycles is rejected; valid plan registers with counts in response.

### Step 5: Expose task graph in `plan(operation="get")`

- Return `task_graph: list[TaskNode]` in the response.
- Include a `can_parallelize: bool` field (True if any `[P]` steps exist with no blocking dependencies on prior incomplete steps).

**Verification**: `plan(operation="get")` returns task graph; `can_parallelize` is True for plans with independent steps.

### Step 6: Update `/cortex/do` orchestrator to exploit parallelism

- In `src/cortex/tools/pipeline_handoff.py` or the do-orchestrator prompt:
  1. Call `plan(operation="get")` to retrieve the task graph.
  2. Identify the current execution frontier: all `[P]` steps whose dependencies are satisfied.
  3. For each frontier step, spawn an `implement-code` subagent with `isolation="worktree"`.
  4. Wait for all frontier agents to complete before advancing.
  5. Sequential steps run one at a time.
- Limit concurrent agents: max 3 parallel worktrees (configurable via session config).

**Verification**: A plan with 3 independent `[P]` steps spawns 3 concurrent agents; sequential steps still run one-at-a-time.

### Step 7: Add worktree merge strategy

- After parallel agents complete, merge their worktrees back to the main branch in dependency order.
- Conflict resolution: if two parallel agents modified the same file, surface the conflict as a `[NEEDS CLARIFICATION]` marker (see clarification markers plan) rather than auto-resolving.

**Verification**: Merge completes for non-conflicting worktrees; conflicts produce clarification markers.

### Step 8: Tests

- Unit: `parse_task_graph` — no markers, `[P]` only, `[P:after=...]`, cycle detection.
- Unit: `can_parallelize` logic.
- Unit: Plan creation marking heuristic (mock `think()` output).
- Integration: Two-step parallel plan → two agents → merge.
- Edge case: All steps sequential (no `[P]`); all steps parallel; mixed.

**Verification**: All tests pass, ≥ 95% coverage on new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `TaskNode` class | `src/cortex/core/models.py` | full file |
| 2 | `parse_task_graph` | `src/cortex/core/plan_utils.py` | full file |
| 3 | `[P]` marker emission | `src/cortex/tools/plan.py` | `create` branch |
| 4 | Cycle validation | `src/cortex/tools/plan.py` | `register` branch |
| 5 | Task graph in `get` | `src/cortex/tools/plan.py` | `get` branch |
| 6 | Parallel agent spawning | orchestrator / `pipeline_handoff.py` | full file |
| 7 | Merge strategy | orchestrator | conflict handling |
| 8 | Test files | `tests/` | new test files |

## Dependencies

- Existing `plan` tool
- Existing `pipeline_handoff` tool
- `implement-code` subagent
- `TaskNode` model (Step 1)
- `parse_task_graph` utility (Step 2)
- Needs Clarification markers plan (for Step 7 conflict handling — optional integration)

## Success Criteria

- Plans with independent steps are marked `[P]` during creation.
- Cycle detection prevents invalid plans from registering.
- `/cortex/do` spawns concurrent agents for `[P]` steps.
- Merge conflicts surface as clarification markers.
- No `Any` types; functions ≤ 30 lines; ≥ 95% coverage.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Parser (all marker variants), cycle detection, frontier computation, `can_parallelize`.
- **Integration**: Parallel agent orchestration with real worktrees (or mocked subagents).
- **Edge cases**: Plan with a single step (no parallelism); step depending on itself (cycle); `[P:after=99]` referencing non-existent step.
