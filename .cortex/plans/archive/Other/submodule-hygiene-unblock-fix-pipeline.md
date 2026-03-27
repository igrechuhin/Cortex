---
title: Submodule Hygiene Unblock for Fix Pipeline
component: tooling
work_type: blocker
status: PENDING
priority: high
created: 2026-03-27
depends_on:
  - session-scope-lock-pattern.md
---

## Goal

Unblock `/cortex/fix` quality and test targets by making `.cortex/synapse` issue-clean for submodule hygiene checks without losing intended prompt updates.

## Context

Root `run_quality_gate()` currently fails at `submodule_hygiene` before type/lint/tests execute. The dirty submodule contains prompt markdown edits that are likely valid work-in-progress but currently block superproject gates.

## Implementation Steps

1. Capture baseline evidence for blocker behavior.
   - Record `run_quality_gate()` output showing `submodule_hygiene` failure.
   - Confirm changed paths in `.cortex/synapse` and classify change scope.

2. Define acceptable hygiene semantics for `/fix` execution.
   - Align expected behavior between prompt guidance and gate implementation.
   - Decide whether to enforce issue-clean vs git-clean semantics at root quality gate.

3. Apply minimal implementation to unblock quality/test execution.
   - Option A: adjust quality gate preflight behavior to route to submodule-first remediation.
   - Option B: adjust fix workflow tooling to auto-handle submodule-first checks before root gate.
   - Preserve existing safety constraints and zero-arg tool behavior.

4. Add/adjust regression tests.
   - Cover dirty-submodule scenario for `/fix` flow.
   - Assert root gate proceeds only after submodule-first remediation criteria are met.

5. Re-verify full sequence.
   - Run `/cortex/fix` path: quality -> tests -> docs.
   - Confirm blocker is resolved and no regressions introduced.

## Verification Checklist

## Step 1

- What to search for: `submodule_hygiene`, `.cortex/synapse`, `run_quality_gate`
- Search scope: `src/`, `tests/`, `.cortex/synapse/prompts/`
- Files to re-read: `src/cortex/tools/execution/pre_commit_zero_arg_tools.py`, `.cortex/synapse/prompts/fix.md`

## Step 2

- What to search for: `/fix clean semantics`, `Submodule-First Fix Routing`
- Search scope: `.cortex/synapse/prompts/`, `docs/guides/`
- Files to re-read: `.cortex/synapse/prompts/fix.md`, `docs/guides/workflows.md`

## Step 3

- What to search for: preflight/submodule guard implementation
- Search scope: `src/cortex/tools/execution/`
- Files to re-read: `src/cortex/tools/execution/pre_commit_zero_arg_tools.py`

## Step 4

- What to search for: governance test expectations for submodule behavior
- Search scope: `tests/`
- Files to re-read: `tests/tools/test_phase4_optimization.py`, `tests/integration/test_commit_workflow_prompt_alignment.py`

## Step 5

- What to search for: passing statuses and failure snippets
- Search scope: MCP tool outputs for quality/tests/docs
- Files to re-read: updated test files and prompt docs touched in this plan

## Dependencies

- Existing dirty submodule changes in `.cortex/synapse`
- `run_quality_gate()` preflight behavior
- Prompt/tooling alignment for `/cortex/fix`

## Success Criteria

- `/cortex/fix` no longer fails immediately due to unresolved submodule hygiene when submodule-first remediation is applicable.
- Quality and tests execute after the blocker is handled.
- Regression tests capture the intended behavior.
- No weakening of safety checks and no duplicate workflow paths.

## Testing Strategy (95% coverage target)

- Add targeted tests around submodule-first routing behavior and preflight transitions.
- Maintain existing coverage thresholds and ensure modified modules stay at or above project quality expectations.
- Include at least one integration scenario validating full `/fix` target order with blocker handling.
