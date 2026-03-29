# Step 6 of 8 — Update python synapse scripts: FILES env var interface parity

**Series**: Per-File Language Quality Gate
**Date Created**: 26-03-29
**Status**: Ready for Implementation
**Depends on**: `swift-qg-s5-swift-check-function-lengths.plan.md`
**Next step**: `swift-qg-s7-unit-tests.plan.md`

---

## Goal

Add the `FILES` environment variable interface to both Python synapse scripts so they
have parity with the updated Swift scripts. This ensures the router can dispatch to
Python scripts the same way it dispatches to Swift scripts.

Two files are updated in this step:

- `.cortex/synapse/scripts/python/check_file_sizes.py`
- `.cortex/synapse/scripts/python/check_function_lengths.py`

---

## Files to Read First

1. `.cortex/synapse/scripts/python/check_file_sizes.py` — full file (183 lines)
2. `.cortex/synapse/scripts/python/check_function_lengths.py` — full file (243 lines)

---

## Files to Modify

| File | Change |
|------|--------|
| `.cortex/synapse/scripts/python/check_file_sizes.py` | Add `FILES` env var branch in `main()` |
| `.cortex/synapse/scripts/python/check_function_lengths.py` | Add `FILES` env var branch in `main()` |

---

## Change Pattern (same for both files)

### 1. Add `_get_files_from_env()` helper

Add before `main()`:

```python
def _get_files_from_env() -> list[Path] | None:
    """Return explicit file list from FILES env var, or None if not set."""
    import os
    files_env = os.environ.get("FILES")
    if not files_env:
        return None
    return [Path(p) for p in files_env.strip().splitlines() if p]
```

(`import os` is at module level in both files already — use it, don't re-import.)

### 2. Update `main()` in `check_file_sizes.py`

**Current structure** (simplified):

```python
src_dir = get_config_path("SRC_DIR") or find_src_directory(project_root)
for py_file in src_dir.glob("**/*.py"):
    ...
```

**New structure**:

```python
files_from_env = _get_files_from_env()
if files_from_env is not None:
    # Dispatcher mode: check exactly these files
    py_files = [f for f in files_from_env if f.suffix == ".py"]
else:
    # Standalone fallback: existing directory scan (unchanged)
    src_dir = get_config_path("SRC_DIR")
    if src_dir is None:
        src_dir = find_src_directory(project_root)
    elif not src_dir.is_absolute():
        src_dir = project_root / src_dir
    if not src_dir.exists():
        print(f"Error: Source directory {src_dir} does not exist", file=sys.stderr)
        sys.exit(1)
    py_files = [
        f for f in src_dir.glob("**/*.py")
        if "__pycache__" not in str(f)
        and not f.name.startswith("test_")
        and f.name not in EXCLUDED_FILENAMES
    ]

for py_file in py_files:
    lines = count_lines(py_file)
    ...
```

> **Interface contract**: When `FILES` is set, scripts check **exactly** those files.
> The dispatcher is responsible for filtering (e.g. excluding `models.py`).
> In dispatcher mode, do NOT apply `test_*` or `EXCLUDED_FILENAMES` filters —
> the router decides what to pass.

### 3. Update `main()` in `check_function_lengths.py`

Same branching pattern:

```python
files_from_env = _get_files_from_env()
if files_from_env is not None:
    py_files = [f for f in files_from_env if f.suffix == ".py"]
else:
    # existing SRC_DIR / find_src_directory() + glob logic (unchanged)
    src_dir = ...
    py_files = [
        f for f in src_dir.glob("**/*.py")
        if "__pycache__" not in str(f)
        and not f.name.startswith("test_")
    ]

for py_file in py_files:
    try:
        rel = str(py_file.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        rel = str(py_file)
    if rel in excluded:
        continue
    ...
```

---

## What Must NOT Change

- The existing directory-scan fallback logic — it must remain identical to today when
  `FILES` is not set. Do not alter exclusion rules, `find_src_directory()` calls, or
  output formatting.
- Output format (stderr strings) — unchanged. The router's parsers depend on them.
- Exit codes: 0 = no violations, 1 = violations found.

---

## Success Criteria

- [ ] `_get_files_from_env()` added to both Python scripts with correct return type
- [ ] When `FILES=/path/to/big.py`, each script checks only that file
- [ ] When `FILES` unset, fallback behavior is identical to before this change
- [ ] Both scripts still pass standalone invocation with no `FILES` env
- [ ] Output format (stderr violation lines) unchanged — parsers still work
- [ ] No `Any` type; all new functions have type hints
- [ ] Each file ≤ 400 lines after changes
- [ ] `run_quality_gate()` passes after these changes
