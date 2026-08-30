---
title: "Session Goal Anchoring with Drift Detection"
component: planning
work_type: feature
status: PENDING
priority: High
created: 2026-04-06
depends_on: []
---

## Goal

Add a `goal.md` written at the start of each session (by `session()`) that captures the single primary goal. Mid-session, if an agent is about to touch files unrelated to that goal, it checks `goal.md` and flags scope drift explicitly before proceeding — rather than silently expanding scope. This gives mechanical enforcement to the existing "single-goal session" discipline in CLAUDE.md.

## Context

Inspired by OpenSpec's explicit separation of `specs/` (current state) vs. `changes/` (desired delta). CLAUDE.md already mandates single-goal sessions, but there is no enforcement mechanism — agents frequently expand scope silently when they encounter related issues. A `goal.md` artifact provides a stable reference point that both agents and humans can consult to detect drift.

## Implementation Steps

### Step 1: Define goal anchor model

- Add `SessionGoal` Pydantic model in `src/cortex/core/models.py`:
  - `goal: str` — one-sentence description of the primary goal.
  - `plan_slug: str | None` — the plan this session is implementing (if any).
  - `allowed_files: list[str]` — glob patterns for files in scope (auto-populated from plan steps).
  - `blocked_files: list[str]` — glob patterns explicitly out of scope.
  - `created_at: datetime`
  - `session_id: str` — UUID, generated at session start.
- File path: `.cortex/session-goal.md` (ephemeral, not committed).

**Verification**: Model defined, fully typed, importable.

### Step 2: Add goal anchoring to `session()`

- Add `goal: str | None` parameter to `session()`.
- If `goal` provided: write `SessionGoal` to `.cortex/session-goal.md`. Auto-populate `allowed_files` from the plan's implementation steps (extract file paths mentioned in steps).
- If not provided: check if an existing `session-goal.md` exists (resuming session) and load it.
- Include the goal anchor in `session()` output: "Current goal: <goal>. Drift detection active."
- If no goal provided and no existing goal file: include a prompt to set one.

**Verification**: `session()` with `goal="..."` creates the goal file; without goal loads existing or prompts.

### Step 3: Add drift detection utility

- Add `check_drift(file_path: str, goal: SessionGoal) -> DriftResult` in `src/cortex/core/drift_detector.py`.
- `DriftResult` model:
  - `drifted: bool`
  - `reason: str`
  - `allowed: bool` (explicit override)
- Logic:
  1. If `file_path` matches any pattern in `allowed_files` → `drifted=False`.
  2. If `file_path` matches any pattern in `blocked_files` → `drifted=True, reason="explicitly blocked"`.
  3. If `file_path` matches no pattern: compute similarity between file's directory and the plan slug / allowed file patterns. If similarity < 0.5 → `drifted=True, reason="unrelated to goal"`.
- Non-blocking: drift is flagged, not prevented.

**Verification**: Drift detection correctly classifies in-scope, out-of-scope, and explicitly blocked files.

### Step 4: Add drift check to `implement-code` subagent

- In the `implement-code` prompt, before writing any file:
  1. Load `session-goal.md` (if present).
  2. Call `check_drift(file_path, goal)`.
  3. If `drifted=True`: emit a warning: `[DRIFT WARNING: editing <file> may be out of scope. Goal: <goal>. Reason: <reason>. Proceed? If yes, explain why in a # AI: comment.]`
  4. Proceed regardless — drift is a warning, not a blocker.

**Verification**: Agent emits drift warning for out-of-scope files; does not block.

### Step 5: Add drift summary to `session()` at end of session

- When `session()` is called with `operation="compact"` (end of session):
  - Read the session goal file.
  - Scan git diff for files touched in this session.
  - For each touched file, run `check_drift`.
  - Report: "Session touched N files: M in scope, K out of scope (drift)."
  - If drift rate > 30%, flag: "High drift detected. Consider splitting into focused sessions."

**Verification**: End-of-session report includes drift summary; high drift triggers flag.

### Step 6: Add `manage_file(operation="set_goal")` and `"clear_goal"`

- `set_goal(goal: str, plan_slug: str | None)`: writes `session-goal.md`.
- `clear_goal()`: deletes `session-goal.md` (call at session end or when goal changes).
- `get_goal()`: reads and returns current goal anchor.

**Verification**: All three operations work correctly.

### Step 7: Surface goal in `cortex://context` resource

- If `session-goal.md` exists, include the goal anchor at the top of the context payload (before memory bank sections).
- This ensures every agent that reads context is aware of the current goal.

**Verification**: Context includes goal anchor; no noise when goal file absent.

### Step 8: Tests

- Unit: `SessionGoal` model validation.
- Unit: `check_drift` — in scope, out of scope, blocked, edge patterns.
- Unit: Goal file write/read/clear.
- Unit: End-of-session drift report — low drift, high drift.
- Integration: `session()` with goal → `implement-code` drift warning → `session(operation="compact")` drift report.

**Verification**: All tests pass, ≥ 95% coverage on new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `SessionGoal`, `DriftResult` | `src/cortex/core/models.py` | full file |
| 2 | Goal anchoring in `session()` | `src/cortex/tools/session.py` | full file |
| 3 | `check_drift` | `src/cortex/core/drift_detector.py` | full file |
| 4 | Drift check in `implement-code` | `.cortex/synapse/cursor-agents/implement-code.md` | full file |
| 5 | End-of-session drift report | `src/cortex/tools/session.py` | `compact` branch |
| 6 | `set_goal`, `clear_goal`, `get_goal` | `src/cortex/tools/manage_file.py` | full file |
| 7 | Goal in context resource | `src/cortex/resources/context.py` | full file |
| 8 | Test files | `tests/` | new test files |

## Dependencies

- Existing `session()` tool
- Existing `manage_file` tool
- Existing `cortex://context` resource
- `implement-code` subagent
- `SessionGoal` model (Step 1)
- `DriftResult` model (Step 3)
- `check_drift` utility (Step 3)

## Success Criteria

- Each session has a named goal anchor written to `session-goal.md`.
- `implement-code` emits drift warnings for out-of-scope files (non-blocking).
- End-of-session compact includes a drift summary.
- High drift rate triggers a session-splitting recommendation.
- No `Any` types; functions ≤ 30 lines; ≥ 95% coverage.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Goal model; drift detection (parametrized: in-scope, out-of-scope, blocked, edge cases like empty allowed_files list).
- **Integration**: Goal write → drift check → end-of-session report.
- **Edge cases**: No goal file (drift detection skips gracefully); goal with empty `allowed_files` (all files flagged as potential drift); `blocked_files` overrides `allowed_files` (blocked wins).
