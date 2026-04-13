# Plan: Migrate check_function_lengths callers to file_language_router

**Status:** PENDING  
**Priority:** P1 — quality gate correctness  
**Created:** 2026-04-13

## Background

`check_function_lengths()` in
`src/cortex/tools/execution/pre_commit_pipeline_quality.py` is a
Python-only, AST-based implementation that predates the language router.
The router path (`run_quality_checks_for_all_languages` →
`check_function_lengths.py` synapse script) is the canonical, multi-language
implementation used by `execute_quality()` in production.

The function carries this TODO (line 267):

> TODO: migrate callers to file_language_router / synapse scripts when tests
> are updated to use the router path exclusively.

Until this migration is complete, two code paths exist for the same check,
and any divergence between them is a silent correctness risk.

## Goal

Remove the `check_function_lengths()` function (or reduce it to a thin
shim) once all callers are routed through `run_quality_checks_for_all_languages`.

## Completion Criteria

- [ ] All test callers of `check_function_lengths()` replaced with router-path equivalents.
- [ ] Parity test passes: both paths produce identical violation sets on a
      synthetic fixture (see `tests/unit/test_check_function_lengths_parity.py`).
- [ ] `check_function_lengths()` either deleted or replaced with a one-line
      shim that delegates to `run_quality_checks_for_all_languages`.
- [ ] TODO comment removed from `pre_commit_pipeline_quality.py`.
- [ ] No regressions in `test_pre_commit_tools.py` or
      `test_file_language_router_dispatch.py`.

## Callers to migrate (as of 2026-04-13)

- `tests/unit/test_pre_commit_tools.py` — imports and calls
  `check_function_lengths` directly (lines 56, 1627, 1646, 1661, 1696, 1715).

## Steps

1. Add parity test (`tests/unit/test_check_function_lengths_parity.py`)
   that asserts both paths return the same violations for a synthetic
   Python fixture with a known-oversized function.
2. Rewrite the `test_pre_commit_tools.py` tests that call
   `check_function_lengths` directly to go through
   `run_quality_checks_for_all_languages` (or `execute_quality`).
3. Confirm parity test passes with both implementations.
4. Delete or shim `check_function_lengths()` and remove TODO comment.
5. Run full test suite (`pytest tests/ -x -q`).

## Risk

Low — both paths already produce zero violations in production; divergence
is only observable when violations are present (test fixtures).
