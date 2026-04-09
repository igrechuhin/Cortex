---
title: "Explore-Before-Commit Workflow (/cortex/explore)"
component: planning
work_type: feature
status: PENDING
priority: high
created: 2026-04-06
depends_on: []
---

## Goal

Add a lightweight `/cortex/explore` phase before `/cortex/plan`. This is a brainstorming mode: no plan files or roadmap entries are committed yet. The agent explores trade-offs, surfaces options, and produces an optional `decision-log.md` artifact in the plan. Only after the user picks a direction does `/cortex/plan` formalize the spec. This prevents premature commitment to the first solution found.

## Context

Inspired by OpenSpec's `/opsx:explore` command. Currently, `/cortex/plan` jumps directly from user intent to a formal plan file. For complex or novel tasks, this is too aggressive — it bakes in the first plausible approach without exploring alternatives. An explicit explore phase separates ideation from commitment.

## Implementation Steps

### Step 1: Define explore session model

- Add `ExploreSession` Pydantic model in `src/cortex/core/models.py`:
  - `topic: str`
  - `options: list[ExploreOption]`
  - `recommendation: str | None`
  - `created: datetime`
  - `decision: str | None` (filled in after user selects)
- Add `ExploreOption` model:
  - `title: str`
  - `description: str`
  - `pros: list[str]`
  - `cons: list[str]`
  - `complexity: Literal["low", "medium", "high"]`
  - `risk: Literal["low", "medium", "high"]`

**Verification**: Models defined, fully typed, importable.

### Step 2: Create `/cortex/explore` prompt

- Add `.cortex/synapse/prompts/explore.md` with the following workflow:
  1. Call `session()` for orientation.
  2. Read `cortex://context` and `cortex://rules`.
  3. Use `think()` to enumerate 2–5 distinct approaches to the user's topic.
  4. For each approach, populate an `ExploreOption`.
  5. Write a `decision-log-<slug>.md` to `.cortex/plans/explore/` (ephemeral directory, not registered in roadmap).
  6. Present options to the user with a recommendation.
  7. If the user selects an option, invoke `/cortex/plan` with the selected approach as context — the decision is recorded in the log.
- No plan file is created; no roadmap entry is made.

**Verification**: Prompt file exists; running it produces an explore log, not a plan file.

### Step 3: Add `explore/` ephemeral directory management

- Add `manage_file(operation="list_explore_logs")` to list `.cortex/plans/explore/*.md`.
- Add `manage_file(operation="clear_explore_logs")` to purge explore logs older than 7 days.
- Explore logs are NOT registered in the roadmap.

**Verification**: List and clear operations work; explore logs are absent from roadmap.

### Step 4: Add decision capture to `plan(operation="create")`

- Accept optional `explore_log_path: str` parameter.
- If provided, read the explore log and prepend a `## Decision Basis` section to the plan explaining which option was selected and why.
- This gives the plan a traceable lineage back to the explore session.

**Verification**: Plan created with `explore_log_path` includes a `## Decision Basis` section.

### Step 5: Add explore log reference to `cortex://context` resource

- If an explore log was referenced in the current session (tracked via session config), include a brief summary in the context payload.
- Helps agents understand the design rationale without re-reading the full log.

**Verification**: Context includes explore summary when log is referenced; no noise otherwise.

### Step 6: Register explore command in `session()` output

- Add a tip in `session()` output: "Use `/cortex/explore` before `/cortex/plan` for complex or novel tasks."
- Only show if no active plan exists for the current task.

**Verification**: Session output includes explore tip at appropriate times.

### Step 7: Tests

- Unit: `ExploreSession` and `ExploreOption` model validation.
- Unit: `list_explore_logs` and `clear_explore_logs` (mock filesystem).
- Unit: Plan creation with `explore_log_path` adds `## Decision Basis`.
- Integration: Full explore → select → plan cycle with temp directory.

**Verification**: All tests pass, ≥ 95% coverage on new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `ExploreSession`, `ExploreOption` | `src/cortex/core/models.py` | full file |
| 2 | `explore.md` prompt | `.cortex/synapse/prompts/` | full file |
| 3 | `list_explore_logs`, `clear_explore_logs` | `src/cortex/tools/manage_file.py` | full file |
| 4 | `explore_log_path` param | `src/cortex/tools/plan.py` | `create` branch |
| 5 | Explore summary in context | `src/cortex/resources/context.py` | full file |
| 6 | Explore tip in session | `src/cortex/tools/session.py` | startup logic |
| 7 | Test files | `tests/` | new test files |

## Dependencies

- Existing `plan` tool
- Existing `session()` tool
- Existing `cortex://context` resource
- `ExploreSession` / `ExploreOption` models (Step 1)

## Success Criteria

- `/cortex/explore` produces an explore log without creating a plan or roadmap entry.
- Selecting an option transitions cleanly to `/cortex/plan` with decision context.
- Plans created from explore sessions include a traceable `## Decision Basis` section.
- Explore logs auto-expire after 7 days.
- No `Any` types; functions ≤ 30 lines; ≥ 95% coverage.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Model validation; file listing/cleanup; plan decision basis injection.
- **Integration**: Explore → plan transition with temp directory.
- **Edge cases**: Explore with 0 options (invalid, should error); explore log missing at plan creation time (graceful skip); all logs expired (empty list returned).
