# Step 3 of 8 — Remove Python guard; wire router into execute_quality()

**Series**: Per-File Language Quality Gate
**Date Created**: 26-03-29
**Status**: Ready for Implementation
**Depends on**: `swift-qg-s2-create-file-language-router.plan.md` (router must exist)
**Next step**: `swift-qg-s4-swift-check-file-sizes.plan.md`

---

## Goal

Remove the `if language == "python":` guard from `execute_quality()` in
`pre_commit_pipeline_quality.py` and replace it with a single call to
`run_quality_checks_for_all_languages()`. This is the one-line fix that closes
the silent false-positive bug.

---

## Files to Read First

1. `src/cortex/tools/execution/pre_commit_pipeline_quality.py` — full file
2. `src/cortex/tools/execution/file_language_router.py` — confirm it exists and exports `run_quality_checks_for_all_languages`
3. `src/cortex/tools/execution/pre_commit_helpers_quality.py` — confirm which of its exports are still used after this change

---

## File to Modify

`src/cortex/tools/execution/pre_commit_pipeline_quality.py`

---

## Exact Changes

### 1. Update imports

**Remove** (if `check_file_sizes` and `check_function_lengths_in_file` are no longer
used anywhere in this file after the change):

```python
from cortex.tools.execution.pre_commit_helpers_quality import (
    check_file_sizes,
    check_function_lengths_in_file,
)
```

**Add**:

```python
from cortex.tools.execution.file_language_router import (
    run_quality_checks_for_all_languages,
)
```

> **Check before removing**: grep the file for any other usages of `check_file_sizes`
> and `check_function_lengths_in_file`. Only remove their imports if they have zero
> remaining call sites in this file.

### 2. Update `execute_quality()`

**Before** (lines ~68-71):

```python
file_violations: list[FileSizeViolation] = []
func_violations: list[FunctionLengthViolation] = []
if language == "python":
    file_violations = check_file_sizes(project_root)
    func_violations = check_function_lengths(project_root)
```

**After**:

```python
file_violations, func_violations = run_quality_checks_for_all_languages(project_root)
```

### 3. Check `_collect_violations_from_file` and `check_function_lengths`

These two private helpers in `pre_commit_pipeline_quality.py` exist only to support
the old Python-only `check_function_lengths(project_root)` call. After the change:

- Grep the entire codebase for `_collect_violations_from_file` and `check_function_lengths`
  (from this module, not from `pre_commit_helpers_quality`).
- If no other file imports them, **delete both functions** from `pre_commit_pipeline_quality.py`.
- If any other file imports them, keep them and leave a `# TODO: migrate to router` comment.

---

## What Must NOT Change

- `check_file_sizes()` and `check_function_lengths_in_file()` in
  `pre_commit_helpers_quality.py` — do not touch that file. Those functions remain
  available for direct use by tests and scripts.
- The `_build_quality_errors()` and `_build_quality_output()` private functions in
  `pre_commit_pipeline_quality.py` — they are unchanged; `execute_quality()` still
  calls them with the violations returned by the router.
- The `execute_quality()` function signature — it still takes `(adapter, language)`.
  The `language` parameter is still passed to `adapter.lint_code()` indirectly.

---

## Success Criteria

- [ ] `pre_commit_pipeline_quality.py` no longer contains `if language == "python":`
- [ ] `execute_quality()` calls `run_quality_checks_for_all_languages(project_root)` unconditionally
- [ ] Imports updated (no unused imports; `file_language_router` import added)
- [ ] `_collect_violations_from_file` and `check_function_lengths` deleted if unused (verified by grep)
- [ ] `run_quality_gate()` passes — Python project checks unchanged
- [ ] File remains ≤ 400 lines; all functions ≤ 30 logical lines
