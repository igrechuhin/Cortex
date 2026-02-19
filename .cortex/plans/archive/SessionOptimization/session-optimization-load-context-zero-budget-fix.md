# Session Optimization: Fix load_context Zero-Budget Configuration Error (Blocker)

## Status

PENDING

## Goal

Fix the critical configuration error where `load_context` is called with `token_budget=0` for non-trivial tasks, resulting in zero effective budget and no memory-bank content loaded. Ensure agents always receive memory-bank guidance for implement/fix/debug/planning tasks.

## Context

From end-of-session analysis (`.cortex/reviews/session-optimization-2026-02-19T19-59.md`):

- **Observed**: `load_context` was invoked with `token_budget=0` for a planning task; 2 files were selected but effective budget was 0, so no content was loaded.
- **Root cause**: `_calculate_effective_budget()` in `src/cortex/tools/phase4_context_operations.py` accepts `token_budget=0` explicitly. When `0` is passed (not `None`), it uses 0 directly and returns `max(0 - reserve, 0) = 0`, so no content is loaded.
- **Impact**: Workflow violation; agents run without memory-bank guidance for non-trivial tasks.

## Approach

1. Add validation in the `load_context` handler to reject `token_budget=0` for non-trivial tasks (or treat 0 as "use default" in budget calculation).
2. Optionally treat `token_budget=0` as `None` in `_calculate_effective_budget` so explicit zero uses default budget.
3. Strengthen implement/analyze prompts with explicit correct vs incorrect budget examples.

## Implementation Steps

Execute in order. Do not skip or reorder.

### Step 1: Add Zero-Budget Validation in load_context Handler (Priority 1)

- **Target**: `src/cortex/tools/phase4_optimization_handlers.py` (load_context handler).
- **Action**: Before calling `load_context_impl`, call `_validate_zero_budget_for_non_trivial(task_description, token_budget)`. If it returns a non-empty error string, return a formatted error (e.g. via `_format_load_context_error(ValueError(message))`) and do not proceed.
- **Acceptance**: For a non-trivial task description and `token_budget=0`, the tool returns a clear error with guidance to use a non-zero budget (e.g. 10k–15k for fix/debug, 20k–30k for implement).

### Step 2: Treat token_budget=0 as None in Effective Budget (Priority 2)

- **Target**: `src/cortex/tools/phase4_context_operations.py`, function `_calculate_effective_budget` (lines 37–54).
- **Action**: Change the condition from `if token_budget is None:` to `if token_budget is None or token_budget == 0:` so that explicit zero is treated as "use default" and `optimization_config.get_token_budget()` is used.
- **Acceptance**: When callers pass `token_budget=0`, effective budget is the same as when passing `None` (default), and content is loaded.

### Step 3: Strengthen Prompt Guidance with Examples (Priority 3)

- **Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` (Step 2: Load relevant context).
- **Action**: Add explicit examples:
  - INCORRECT: `load_context(task_description="...", token_budget=0)`.
  - CORRECT: `load_context(task_description="...", token_budget=10000)` or `load_context(task_description="...")` (uses default).
- **Target**: `.cortex/synapse/prompts/analyze.md` if it references load_context budget; add same style examples if applicable.
- **Acceptance**: Prompts contain at least one INCORRECT/CORRECT pair for token_budget usage.

### Step 4: Add Tests

- **Target**: `tests/tools/test_phase4_optimization.py` (or equivalent phase4 tests).
- **Action**:
  - Test that for a non-trivial task description, `load_context(..., token_budget=0)` returns a validation error (after Step 1).
  - Test that when `_calculate_effective_budget` is called with `token_budget=0`, the result equals the result when called with `token_budget=None` (after Step 2).
  - Test that trivial task with zero budget (if allowed by policy) still behaves as specified.
- **Acceptance**: New/updated tests pass; coverage for new branches meets project threshold (e.g. 95% for new code).

### Step 5: Update Documentation

- **Target**: `docs/api/tools.md` (load_context section).
- **Action**: State that `token_budget=0` is either rejected for non-trivial tasks (Step 1) or treated as "use default" (Step 2); document validation behavior and recommend non-zero budgets for implement/fix/debug/planning.
- **Acceptance**: load_context docs clearly describe zero-budget behavior and recommendations.

## Dependencies

- None. Uses existing `_validate_zero_budget_for_non_trivial` and optimization config.

## Success Criteria

- Non-trivial tasks cannot receive zero effective budget due to `token_budget=0` (either rejected or normalized to default).
- Implement and analyze prompts include explicit INCORRECT/CORRECT budget examples.
- Tests cover validation and effective-budget behavior; quality gate passes.
- docs/api/tools.md reflects current behavior.

## Testing Strategy

- **Coverage target**: Minimum 95% for new/updated code in phase4 handlers and phase4_context_operations.
- **Unit tests**: Validation path (handler), `_calculate_effective_budget(0)` vs `_calculate_effective_budget(None)`.
- **Integration tests**: One end-to-end `load_context` call with `token_budget=0` and non-trivial task description (expect error or default budget behavior per implementation).
- **Edge cases**: Trivial task + zero budget (if allowed); empty task description; role-based behavior unchanged.
- **Regression**: Existing load_context tests still pass; no regression in default or metadata_only behavior.

## Risks and Mitigation

- **Risk**: Callers intentionally pass 0 for "no context" and break. **Mitigation**: Step 2 (treat 0 as None) preserves backward compatibility by loading default budget; Step 1 can be limited to returning a warning instead of hard error if product requires.
- **Risk**: Duplicate logic with existing "load_context budget" roadmap item. **Mitigation**: This plan is the code + validation fix; the existing "Session Optimization: load_context Budget and Test Type Narrowing" is doc/prompt-focused; keep scope distinct.

## Timeline

Single session (small scope: one config fix, one helper change, prompt and doc edits, tests).

## Notes

- Blocker priority: Ensures agents always get memory-bank context for non-trivial work; without this fix, zero-budget calls repeat and workflow violations continue.
- Reference: `.cortex/reviews/session-optimization-2026-02-19T19-59.md`.
