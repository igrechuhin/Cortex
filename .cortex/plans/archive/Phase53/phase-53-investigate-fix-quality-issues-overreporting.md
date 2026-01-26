# Phase 53 Blocker: Investigate `fix_quality_issues` over-reporting remaining issues

**Date:** 2026-01-25  
**Status:** ✅ COMPLETE (2026-01-26)  
**Priority:** ASAP (can mislead / block mandatory agent workflow)

---

## Problem

`fix_quality_issues()` returns `status="success"` but reports a large `"remaining_issues"` count even when the repository is otherwise green.

Example repro (local, via Python coroutine call):

- `./.venv/bin/python -c "import asyncio; from cortex.tools.pre_commit_tools import fix_quality_issues; print(asyncio.run(fix_quality_issues(project_root='.', include_untracked_markdown=True)))"`

Observed output (abridged):

- `"status": "success"`
- `"errors_fixed": 2088`
- `"type_errors_fixed": 2087`
- `"files_modified": []`
- `"remaining_issues": ["4175 errors remain after auto-fix"]`

At the same time:

- `pyright src` reports **0 errors**
- Full test suite passes and coverage gate is met (≥90%)

---

## Why this matters

Repo agent rules require automatically invoking `fix_quality_issues()` as part of the workflow. If the tool reports large remaining issues while the repo is clean, agents may:

- stop work prematurely
- open unnecessary follow-up plans
- treat the workspace as broken

---

## Hypotheses (most likely)

- The tool uses `"total_errors"`/`"total_warnings"` from `execute_pre_commit_checks()` as “remaining issues”, but those counters may not mean what the fixer assumes (e.g., may include warnings/errors from checks not actually run or from stale cached output).
- The code path that extracts counts (`_extract_fix_statistics()` / `_collect_remaining_issues()`) may misinterpret the JSON payload shape (e.g., `total_errors` is present but not the count of *remaining* problems).
- The underlying adapter methods (`fix_errors`, `format_code`, `type_check`) may report “errors” as lists of messages even when `success=True`, and the fixer counts them as remaining.

---

## Investigation steps

1. Reproduce deterministically in a focused unit test:
   - Extend `tests/unit/test_pre_commit_tools.py` with a test that runs `fix_quality_issues()` and asserts:
     - repo is type-clean (`pyright src` 0 errors) and
     - the tool does not claim large remaining errors (or returns a clearly defined warning field instead).
2. Inspect the `execute_pre_commit_checks()` JSON payload in the fixer:
   - log/print (in test) the decoded dict (bounded) and verify what `total_errors`, `results.fix_errors.errors`, and `results.type_check.errors` contain.
3. Decide correct semantics:
   - If checks ran but errors remain: keep `"remaining_issues"`.
   - If checks are clean: ensure `"remaining_issues"` is empty.
   - If checks are unavailable/failed: return `status="error"` with `error_message`.
4. Implement a fix in `src/cortex/tools/pre_commit_tools.py`:
   - tighten the “tool failure vs normal result” detection for `execute_pre_commit_checks()`
   - compute remaining issues from *actual* failure indicators (e.g., `success` flags / error arrays) rather than broad counters, if those counters are unreliable.
5. Validate:
   - `fix_quality_issues()` returns consistent results on a clean repo
   - existing tests continue to pass

---

## Exit criteria

- On a clean repo (pyright clean, tests pass), `fix_quality_issues()` returns `status="success"` with `remaining_issues=[]`.
- On a broken repo, `remaining_issues` reflects real remaining problems (or returns `status="error"` if tool execution failed).
- Unit tests cover the regression.

## Solution Implemented (2026-01-26)

**Root Cause**: The `_collect_remaining_issues()` function was using aggregate `total_errors`/`total_warnings` counters from `execute_pre_commit_checks()`, which count ALL errors/warnings from ALL checks, not just the ones that remain after auto-fix. These counters can be non-zero even when all checks succeeded (success=True) because they aggregate counts from all checks.

**Fix**: Modified `_collect_remaining_issues()` to check actual check results instead of aggregate counters:

- Check each check result's `success` field and `errors` list
- Only report remaining issues if `success=False` OR if `success` is missing but errors exist
- Use specific error messages for each check type (linting/formatting, formatting, type errors)
- This ensures that `remaining_issues` only contains actual remaining problems, not aggregate counts

**Changes**:

- Updated `_collect_remaining_issues()` in `src/cortex/tools/pre_commit_tools.py` to check individual check results
- Added unit test `test_fix_quality_issues_clean_repo_no_remaining_issues` to verify fix works on clean repo
- Updated existing test to match new, more specific error messages
- All tests passing (5 tests in TestFixQualityIssues class)

**Verification**:

- ✅ On clean repo with all checks succeeded (success=True), `remaining_issues=[]` even if `total_errors` is large
- ✅ On broken repo with actual errors, `remaining_issues` correctly reports remaining problems
- ✅ Unit tests cover the regression
