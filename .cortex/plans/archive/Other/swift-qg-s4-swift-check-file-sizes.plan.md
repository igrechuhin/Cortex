# Step 4 of 8 — Update swift/check_file_sizes.py: FILES env var + Tests/ inclusion

**Series**: Per-File Language Quality Gate
**Date Created**: 26-03-29
**Status**: Ready for Implementation
**Depends on**: `swift-qg-s3-update-pipeline-quality.plan.md`
**Next step**: `swift-qg-s5-swift-check-function-lengths.plan.md`

---

## Goal

Update `.cortex/synapse/scripts/swift/check_file_sizes.py` to:

1. Accept a `FILES` environment variable containing a newline-separated list of
   absolute file paths to check (dispatcher mode).
2. Fall back to directory scanning (`Sources/` **and** `Tests/`) when `FILES` is absent
   (standalone / CI mode).
3. Remove the `Tests/` exclusion from `is_excluded()` so test files are always checked.

---

## Files to Read First

1. `.cortex/synapse/scripts/swift/check_file_sizes.py` — full file (137 lines)

---

## File to Modify

`.cortex/synapse/scripts/swift/check_file_sizes.py`

---

## Exact Changes

### 1. Add `import os` at top

After `import sys` add:

```python
import os
```

### 2. Add `_get_files_from_env()` helper

Add this function before `main()`:

```python
def _get_files_from_env() -> list[Path] | None:
    """Return explicit file list from FILES env var, or None if not set.

    Returns:
        List of Paths when FILES is set and non-empty; None otherwise.
    """
    files_env = os.environ.get("FILES")
    if not files_env:
        return None
    return [Path(p) for p in files_env.strip().splitlines() if p]
```

### 3. Update `is_excluded()` — remove Tests/ guard

**Before**:

```python
def is_excluded(path: Path) -> bool:
    if any(path.name.endswith(s) for s in _GENERATED_SUFFIXES):
        return True
    if "Tests" in path.parts:
        return True
    return False
```

**After**:

```python
def is_excluded(path: Path) -> bool:
    """Return True if this file should be skipped (generated files only)."""
    return any(path.name.endswith(s) for s in _GENERATED_SUFFIXES)
```

### 4. Update `main()` — branch on FILES env var

Replace the block that builds the `swift_files` list from:

```python
for swift_file in sorted(sources_dir.rglob("*.swift")):
    if is_excluded(swift_file):
        continue
    ...
```

To:

```python
files_from_env = _get_files_from_env()
if files_from_env is not None:
    # Dispatcher mode: check exactly these files
    swift_files = [f for f in files_from_env if f.suffix == ".swift" and not is_excluded(f)]
else:
    # Standalone fallback: scan Sources/ and Tests/
    if not sources_dir.exists():
        print(f"❌ Sources directory not found: {sources_dir}", file=sys.stderr)
        sys.exit(1)
    swift_files = [
        f for f in sorted(sources_dir.rglob("*.swift"))
        if not is_excluded(f)
    ]
    # Also include Tests/ if it exists alongside Sources/
    tests_dir = sources_dir.parent / "Tests"
    if tests_dir.exists():
        swift_files += [
            f for f in sorted(tests_dir.rglob("*.swift"))
            if not is_excluded(f)
        ]

for swift_file in swift_files:
    lines = count_logical_lines(swift_file)
    if lines > MAX_FILE_LINES:
        violations.append((swift_file, lines))
    elif lines > WARN_FILE_LINES:
        warnings_list.append((swift_file, lines))
```

> **Note**: In dispatcher mode, the `sources_dir` existence check is skipped entirely —
> the caller has already resolved the files to check.

---

## Interface Contract

| `FILES` env | Behaviour |
|-------------|-----------|
| Not set | Scan `Sources/` and `Tests/` (standalone/CI fallback) |
| Set to non-empty | Check exactly those files; only `.swift` files are kept |
| Set to empty string | Treated as not set; fallback scanning is used |

---

## Success Criteria

- [ ] `_get_files_from_env()` function present and returns `list[Path] | None`
- [ ] `is_excluded()` no longer contains `"Tests" in path.parts`
- [ ] When `FILES=/path/to/Big.swift`, script checks only `Big.swift`
- [ ] When `FILES` is unset and `Tests/` exists, test files are scanned
- [ ] Script still exits 0 on clean project (standalone run, `Sources/` only, no violations)
- [ ] Script still exits 1 when violations found (standalone run)
- [ ] No `Any` type; all new functions have type hints
- [ ] File ≤ 400 lines after changes
