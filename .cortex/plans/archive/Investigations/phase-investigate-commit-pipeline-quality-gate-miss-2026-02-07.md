# Investigation: Commit Pipeline Let Quality Gate Issues Pass (2026-02-07)

## Summary

CI run [21777652000](https://github.com/igrechuhin/Cortex/actions/runs/21777652000) failed with "Type check failed for tests or scripts" and "One or more quality checks failed." The commit pipeline had run locally and reported all steps passing (type check 0 errors, quality passed, tests passed). This plan documents why the pipeline did not catch the same failures CI reported.

## Root Cause: Type-Check Scope Mismatch

### CI type-check steps (quality.yml)

1. **Type check (source)**  
   - Runs: `uv run pyright --outputjson src/`  
   - Scope: `src/` only.

2. **Type check (tests and scripts)**  
   - Runs: `uv run python .cortex/synapse/scripts/python/check_types.py`  
   - Scope: **src + tests + `.cortex/synapse/scripts`** (see `check_types.get_directories_to_check()`: `src_dir`, `tests_dir`, `scripts_dir` from `get_synapse_scripts_dir()`).

### Commit pipeline type-check (Python adapter)

- **Runs**: `pyright src/ tests/` (single invocation in `PythonAdapter.type_check()`).
- **Scope**: `src/` and `tests/` only. **Does not include `.cortex/synapse/scripts`.**

So:

- Type errors in **`.cortex/synapse/scripts`** are checked in CI (step 2) but **never** checked by the commit pipeline.
- Any such error will cause CI to fail with "Type check failed for tests or scripts" even though the pipeline reported type_check passed.

## Evidence

- **quality.yml** (lines 88–95, 183–195): CI runs `pyright src/` then `check_types.py` for "tests and scripts"; the script is the one that includes synapse scripts.
- **check_types.py** (`get_directories_to_check()`): Appends `scripts_dir = get_synapse_scripts_dir(project_root)` (`.cortex/synapse/scripts`) to the list of directories passed to pyright.
- **python_adapter.py** (`type_check()`): Runs `[pyright, "src/", "tests/"]` only; no use of `check_types.py` and no synapse scripts path.

## Fix (Implemented)

Align the commit pipeline with CI by using the same type-check scope:

- In **PythonAdapter.type_check()**, run **`.cortex/synapse/scripts/python/check_types.py`** when that script exists (same as CI’s "tests and scripts" step), so scope is **src + tests + synapse scripts**.
- Keep a fallback to the current `pyright src/ tests/` behavior when the script is missing (e.g. no Synapse submodule).

This way the pipeline type_check matches CI and will fail on the same type errors (including in synapse scripts).

## Related

- Commit prompt states Step 12.2 uses `execute_pre_commit_checks(checks=["type_check"])` and that it "checks BOTH src/ AND tests/ to match CI". The wording is updated to reflect that CI also type-checks **scripts** via `check_types.py`, and the adapter is updated to match.
- Optional follow-up: add a brief note in the commit prompt or agent that type_check includes synapse scripts when the script is present.
