# Step 5 of 8 — Update swift/check_function_lengths.py: FILES env var + Tests/ inclusion

**Series**: Per-File Language Quality Gate
**Date Created**: 26-03-29
**Status**: Ready for Implementation
**Depends on**: `swift-qg-s4-swift-check-file-sizes.plan.md`
**Next step**: `swift-qg-s6-python-scripts-files-env.plan.md`

---

## Goal

Update `.cortex/synapse/scripts/swift/check_function_lengths.py` to:

1. Accept a `FILES` environment variable (newline-separated absolute paths).
2. Fall back to scanning `Sources/` **and** `Tests/` when `FILES` is absent.
3. Remove the `if "Tests" in swift_file.parts: continue` exclusion from the
   directory-scan loop.

This is the same change pattern as Step 4, applied to the function-length script.

---

## Files to Read First

1. `.cortex/synapse/scripts/swift/check_function_lengths.py` — full file (169 lines)

---

## File to Modify

`.cortex/synapse/scripts/swift/check_function_lengths.py`

---

## Exact Changes

### 1. Add `import os`

After `import re` / `import sys`:

```python
import os
```

### 2. Add `_get_files_from_env()` helper

Add before `main()` (identical to Step 4):

```python
def _get_files_from_env() -> list[Path] | None:
    """Return explicit file list from FILES env var, or None if not set."""
    files_env = os.environ.get("FILES")
    if not files_env:
        return None
    return [Path(p) for p in files_env.strip().splitlines() if p]
```

### 3. Update `main()` — replace directory scan with env-var branch

Current scan loop in `main()`:

```python
for swift_file in sorted(sources_dir.rglob("*.swift")):
    if any(swift_file.name.endswith(s) for s in _GENERATED_SUFFIXES):
        continue
    if "Tests" in swift_file.parts:
        continue
    all_violations.extend(check_file(swift_file, project_root))
```

Replace with:

```python
files_from_env = _get_files_from_env()
if files_from_env is not None:
    # Dispatcher mode: check exactly these files
    swift_files = [
        f for f in files_from_env
        if f.suffix == ".swift"
        and not any(f.name.endswith(s) for s in _GENERATED_SUFFIXES)
    ]
else:
    # Standalone fallback: scan Sources/ and Tests/
    if not sources_dir.exists():
        print(f"❌ Sources directory not found: {sources_dir}", file=sys.stderr)
        sys.exit(1)
    swift_files = [
        f for f in sorted(sources_dir.rglob("*.swift"))
        if not any(f.name.endswith(s) for s in _GENERATED_SUFFIXES)
    ]
    tests_dir = sources_dir.parent / "Tests"
    if tests_dir.exists():
        swift_files += [
            f for f in sorted(tests_dir.rglob("*.swift"))
            if not any(f.name.endswith(s) for s in _GENERATED_SUFFIXES)
        ]

for swift_file in swift_files:
    all_violations.extend(check_file(swift_file, project_root))
```

> Note: The `sources_dir` resolution block that currently runs before the loop remains
> in place — it is still needed for the fallback path. In dispatcher mode it is computed
> but unused, which is acceptable (it reads one env var and constructs a Path).

---

## Interface Contract

| `FILES` env | Behaviour |
|-------------|-----------|
| Not set | Scan `Sources/` and `Tests/` |
| Set to non-empty | Check exactly those `.swift` files (generated suffixes excluded) |
| Set to empty string | Treated as not set; fallback used |

---

## Success Criteria

- [ ] `_get_files_from_env()` present with correct return type `list[Path] | None`
- [ ] `"Tests" in swift_file.parts` exclusion removed from scan loop
- [ ] `Tests/` directory is included in fallback scan when it exists
- [ ] When `FILES=/path/to/TestFoo.swift`, that file is checked
- [ ] Script exits 0 on clean project (no violations)
- [ ] Script exits 1 when violations found
- [ ] No `Any` type; all new functions have type hints
- [ ] File ≤ 400 lines after changes
