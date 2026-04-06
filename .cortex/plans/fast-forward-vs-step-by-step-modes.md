---
title: "Fast-Forward vs. Step-by-Step Planning Modes"
component: planning
work_type: feature
status: PENDING
priority: low
created: 2026-04-06
depends_on: []
---

## Goal

Let users choose planning depth at `/cortex/plan` invocation time:

- `--ff` (fast-forward): generate all plan sections in one shot (current behavior, suitable for clear scope).
- `--step`: generate one plan section at a time, pausing for human review between each.

The current behavior is always fast-forward. `--step` mode is needed for complex or high-stakes tasks where premature commitment to a section leads to wasted implementation effort.

## Context

Inspired by OpenSpec's distinction between `/opsx:ff` (fast-forward) and `/opsx:continue` (one artifact at a time). The insight is that planning confidence varies by task: trivial refactors benefit from fast-forward while novel architectural decisions benefit from iterative, human-validated planning. A single mode fits neither case well.

## Implementation Steps

### Step 1: Define planning mode model

- Add `PlanningMode` enum in `src/cortex/core/models.py`:
  - `FAST_FORWARD = "ff"` — generate all sections at once.
  - `STEP_BY_STEP = "step"` — generate one section at a time.
- Add `PlanSection` model:
  - `name: str` (e.g., "goal", "context", "steps", "verification", "testing")
  - `status: Literal["pending", "draft", "approved", "skipped"]`
  - `content: str`
  - `approved_at: datetime | None`

**Verification**: Enum and model defined, importable, fully typed.

### Step 2: Update `plan(operation="create")` to accept `mode` parameter

- Add `mode: PlanningMode = PlanningMode.FAST_FORWARD` parameter.
- **Fast-forward**: existing behavior — write all sections, create file, register in roadmap.
- **Step-by-step**:
  1. Write only the `## Goal` section to a draft file `.cortex/plans/draft-<slug>.md`.
  2. Return the draft content to the user with a prompt: "Review the Goal section. Reply 'ok' or provide corrections, then I'll generate the next section."
  3. On next invocation (with `operation="continue_step"`, `plan_slug="<slug>"`), generate the next pending section.
  4. Repeat until all sections are approved.
  5. Move `draft-<slug>.md` → `<slug>.md` and register in roadmap.

**Verification**: `--ff` produces a complete plan file; `--step` produces a draft with only the Goal section.

### Step 3: Add `plan(operation="continue_step")`

- Reads the draft plan, finds the next `pending` section.
- Generates content for that section using prior approved sections as context.
- Writes the section to the draft file with status `draft`.
- Returns the section to the user for review.

**Verification**: Each call generates exactly one new section; prior sections are not re-generated.

### Step 4: Add `plan(operation="approve_step")`

- Accepts `plan_slug: str`, `section: str`, `corrections: str | None`.
- If `corrections` provided: regenerate the section incorporating corrections, then set status to `draft` again.
- If no corrections: set section status to `approved`.
- Returns next pending section (if any) or "all sections approved — finalizing plan."

**Verification**: Corrections trigger regeneration; no corrections transition to approved; all-approved triggers finalization.

### Step 5: Add `plan(operation="finalize_step")`

- Moves draft file to final location.
- Registers plan in roadmap.
- Cleans up draft file.

**Verification**: Final file exists, draft file removed, roadmap updated.

### Step 6: Update the `/cortex/plan` prompt

- Add instructions for selecting mode:
  - Default (no flag): fast-forward.
  - Explicit `--step` in user message: step-by-step.
  - Heuristic: if the plan topic includes "architecture", "redesign", "migration", or "security", suggest step-by-step.
- Include a note in the plan prompt about how to continue a step-by-step session.

**Verification**: Prompt file updated; heuristic triggers step suggestion for architectural topics.

### Step 7: Add draft file cleanup

- Add `manage_file(operation="list_drafts")` to list `.cortex/plans/draft-*.md`.
- Add `manage_file(operation="discard_draft", plan_slug="<slug>")` to delete a draft.
- `session()` includes a note if stale drafts exist (older than 48 hours): "N stale plan drafts exist. Run `manage_file(operation='list_drafts')` to review."

**Verification**: List and discard operations work; session includes stale draft notice.

### Step 8: Tests

- Unit: `PlanningMode` enum; `PlanSection` model.
- Unit: `create` with `mode=FAST_FORWARD` — existing behavior unchanged.
- Unit: `create` with `mode=STEP_BY_STEP` — only Goal section in draft.
- Unit: `continue_step` — generates next section, preserves prior.
- Unit: `approve_step` — with and without corrections.
- Unit: `finalize_step` — moves draft, registers, cleans up.
- Integration: Full step-by-step cycle: create → 3x continue → 3x approve → finalize.

**Verification**: All tests pass, ≥ 95% coverage on new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `PlanningMode`, `PlanSection` | `src/cortex/core/models.py` | full file |
| 2 | `mode` param in `create` | `src/cortex/tools/plan.py` | `create` branch |
| 3 | `continue_step` operation | `src/cortex/tools/plan.py` | new branch |
| 4 | `approve_step` operation | `src/cortex/tools/plan.py` | new branch |
| 5 | `finalize_step` operation | `src/cortex/tools/plan.py` | new branch |
| 6 | Mode selection in prompt | `.cortex/synapse/prompts/plan.md` | full file |
| 7 | Draft management | `src/cortex/tools/manage_file.py` | full file |
| 8 | Test files | `tests/` | new test files |

## Dependencies

- Existing `plan` tool (all operations)
- Existing `manage_file` tool
- Existing `/cortex/plan` prompt
- `PlanningMode` enum and `PlanSection` model (Step 1)

## Success Criteria

- `--ff` mode produces a complete plan in one shot (existing behavior preserved).
- `--step` mode generates one section at a time with human review between each.
- Stale drafts are surfaced in `session()` and can be discarded.
- No `Any` types; functions ≤ 30 lines; ≥ 95% coverage.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Mode dispatch; section ordering; approval state machine.
- **Integration**: Full step-by-step cycle with temp directory.
- **Edge cases**: Fast-forward with corrections (invalid — corrections only apply in step mode); step mode with all sections skipped (finalize produces minimal plan); draft interrupted mid-session (resume works).
