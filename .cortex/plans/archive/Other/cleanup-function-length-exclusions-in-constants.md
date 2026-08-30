---
title: Cleanup Function-Length Exclusions in Constants
component: quality-gate
work_type: refactor
status: PENDING
priority: High
created: 2026-04-07
depends_on: []
---

## Goal

Remove brittle test-file path exclusions from `FUNCTION_LENGTH_EXCLUDED_PATHS` in `src/cortex/core/constants.py` and replace them with a clearer, policy-aligned mechanism that keeps function-length governance strict for source while handling test ergonomics explicitly.

## Context

Recent quality fixes added test-file exclusions in `constants.py` for `tests/tools/test_file_operations.py` and `tests/tools/test_phase4_optimization.py`. This unblocks gates short-term but creates policy drift and hides long-function debt in tests behind global excludes.

Target exclusion block:

- `src/cortex/core/constants.py:66-76`

Relevant checker path:

- `.cortex/synapse/scripts/python/check_function_lengths.py`

## Implementation Steps

1. Baseline and classify current behavior
   - Confirm how dispatcher mode (`FILES` env) and fallback scan differ for test files.
   - Capture whether test files are intentionally in scope for function-length checks in each mode.

2. Define final policy for test files
   - Choose one explicit policy and document it:
     - A) tests are checked but with a separate threshold, or
     - B) tests are excluded by checker logic (not constants path list), or
     - C) selected long tests are refactored under the same 30-line limit.
   - Prefer policy encoded close to checker logic, not global path constants.

3. Refactor exclusion mechanism
   - Remove ad-hoc test file entries from `FUNCTION_LENGTH_EXCLUDED_PATHS`.
   - Implement the chosen policy in checker/router logic with minimal branching.
   - Keep exclusion constants narrowly focused on true dispatcher modules.

4. Add/adjust tests
   - Update unit tests for checker dispatch behavior and exclusion semantics.
   - Add regression test proving constants no longer carry one-off test-file paths.

5. Verify quality and docs
   - Run quality gate and ensure no new regressions.
   - Confirm docs/memory-bank checks remain green if any prompt/rule text is updated.

## Verification Checklist

### Step 1

- What to search for: `FUNCTION_LENGTH_EXCLUDED_PATHS`, `FILES`, `test_*.py`
- Search scope: `src/cortex/`, `.cortex/synapse/scripts/python/`, `tests/unit/synapse/`
- Files to re-read: `src/cortex/core/constants.py`, `.cortex/synapse/scripts/python/check_function_lengths.py`

### Step 2

- What to search for: policy mentions in rules/prompts and existing tests asserting current behavior
- Search scope: `.cortex/synapse/rules/`, `.cortex/synapse/prompts/`, `tests/`
- Files to re-read: relevant rule/prompt snippets + `tests/unit/synapse/test_python_check_function_lengths_files_env.py`

### Step 3

- What to search for: exclusion list usage + checker call sites
- Search scope: `src/cortex/tools/execution/`, `.cortex/synapse/scripts/python/`
- Files to re-read: updated `constants.py` and checker script

### Step 4

- What to search for: tests asserting old exclusion behavior
- Search scope: `tests/unit/synapse/`, `tests/unit/tools/execution/`
- Files to re-read: modified/new test files

### Step 5

- What to search for: quality/docs gate outputs and failing snippets
- Search scope: MCP gate outputs
- Files to re-read: only files touched during this plan's implementation

## Dependencies

- Existing quality gate architecture for Python checker dispatch
- Current governance limits (`MAX_FUNCTION_LINES = 30`)
- No conflict with ongoing roadmap blockers

## Success Criteria

- No test-file-specific entries remain in `FUNCTION_LENGTH_EXCLUDED_PATHS`.
- Function-length policy for tests is explicit, deterministic, and covered by tests.
- `run_quality_gate()` passes with zero new quality/test regressions.
- Any behavior change is documented where contributors expect enforcement semantics.

## Testing Strategy (95% Coverage Target)

- Unit tests for checker behavior in both fallback and `FILES` dispatcher modes.
- Regression test for constants exclusion set scope.
- Run targeted tests around checker + full quality gate validation.
- Ensure modified modules and new policy branch paths maintain at least 95% coverage in touched logic.

## Notes for Implementation Agents

When implementing this plan, add `# AI:` comments only where non-obvious policy decisions are encoded (why the policy is chosen), not for straightforward refactors.
