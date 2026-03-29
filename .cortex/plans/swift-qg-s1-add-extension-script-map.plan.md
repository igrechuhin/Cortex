# Step 1 of 8 — Add EXTENSION_SCRIPT_MAP to constants.py

**Series**: Per-File Language Quality Gate
**Date Created**: 26-03-29
**Status**: Ready for Implementation
**Depends on**: nothing (first step)
**Next step**: `swift-qg-s2-create-file-language-router.plan.md`

---

## Goal

Add the `EXTENSION_SCRIPT_MAP` constant to `src/cortex/core/constants.py`.
This is the single source of truth that maps file extensions to their synapse
script language directory. Every subsequent step imports from here.

---

## Context

The quality gate currently has a `if language == "python"` guard in
`pre_commit_pipeline_quality.py` (line 69) that silently skips all non-Python files.
Fixing it requires a per-extension routing table. This step adds that table.

---

## Files to Read First

1. `src/cortex/core/constants.py` — full file (understand structure, find insertion point)

---

## Files to Modify

| File | Change |
|------|--------|
| `src/cortex/core/constants.py` | Add `EXTENSION_SCRIPT_MAP` after `FILE_SIZE_EXCLUDED_FILENAMES` |

---

## Exact Change

In `src/cortex/core/constants.py`, after the line:

```python
FILE_SIZE_EXCLUDED_FILENAMES: tuple[str, ...] = ("models.py",)  # Pydantic schema-heavy
```

Insert:

```python
# Maps file extension → synapse script language subdirectory.
# Used by file_language_router to dispatch quality checks per extension.
# Add a new entry here to enable quality checks for a new language.
EXTENSION_SCRIPT_MAP: dict[str, str] = {
    ".py":    "python",
    ".swift": "swift",
}
```

If `__all__` exists in the file, add `"EXTENSION_SCRIPT_MAP"` to it.

---

## Correctness Notes

- The key is the file extension including the leading dot (`.py`, not `py`).
- The value is the directory name under `.cortex/synapse/scripts/` (e.g. `python`, `swift`).
- Type is `dict[str, str]` — O(1) lookup per file extension in the router.
- Do NOT add entries for languages that do not yet have synapse scripts under
  `.cortex/synapse/scripts/<language>/check_file_sizes.py` and
  `.cortex/synapse/scripts/<language>/check_function_lengths.py`.

---

## Verification

After the change:

```python
from cortex.core.constants import EXTENSION_SCRIPT_MAP
assert EXTENSION_SCRIPT_MAP[".py"] == "python"
assert EXTENSION_SCRIPT_MAP[".swift"] == "swift"
assert ".js" not in EXTENSION_SCRIPT_MAP
```

Run `run_quality_gate()` — must pass with zero errors (this is a pure additive change).

---

## Success Criteria

- [ ] `EXTENSION_SCRIPT_MAP` is present in `constants.py` with `.py` and `.swift` entries
- [ ] Type annotation is `dict[str, str]` (no `Any`)
- [ ] `run_quality_gate()` passes after the change
- [ ] No other file is modified in this step
