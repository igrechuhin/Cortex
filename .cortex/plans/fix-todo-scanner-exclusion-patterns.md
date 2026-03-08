# Fix TODO Scanner Overly Broad Exclusion Patterns

**Status**: PENDING
**Priority**: Critical
**Complexity**: Low
**Category**: Fix
**Component**: validation/roadmap_sync
**Work Type**: fix
**Execution Order**: 1

## Goal

Replace substring-based TODO exclusion patterns with word-boundary or path-segment-aware patterns to prevent false negatives on production files containing substrings like "test", "example", "sample", or "demo".

## Context

- `src/cortex/validation/roadmap_sync.py` lines 99-104 define `_EXCLUDE_PATTERNS` using bare substring matching:

  ```python
  _EXCLUDE_PATTERNS = [
      re.compile(r"test", re.IGNORECASE),
      re.compile(r"example", re.IGNORECASE),
      re.compile(r"sample", re.IGNORECASE),
      re.compile(r"demo", re.IGNORECASE),
  ]
  ```

- `_is_production_file()` (line 107-117) returns `False` if any pattern matches anywhere in the file path.
- A file like `src/contest/runner.py`, `src/latest_metrics.py`, or `src/demonstration.py` would be incorrectly excluded.
- External review (2026-03-07) classified this as **Critical** severity.

## Implementation Steps

### Step 1: Replace exclusion patterns with path-segment-aware rules

**File**: `src/cortex/validation/roadmap_sync.py` (lines 99-117)

Replace `_EXCLUDE_PATTERNS` with patterns that match directory segments and file naming conventions:

```python
_EXCLUDE_PATTERNS = [
    re.compile(r"(^|/)tests?/", re.IGNORECASE),        # test/ or tests/ directory
    re.compile(r"(^|/)test_[^/]+\.py$", re.IGNORECASE), # test_*.py files
    re.compile(r"(^|/)conftest\.py$", re.IGNORECASE),    # conftest.py
    re.compile(r"(^|/)examples?/", re.IGNORECASE),       # example/ or examples/ directory
    re.compile(r"(^|/)samples?/", re.IGNORECASE),        # sample/ or samples/ directory
    re.compile(r"(^|/)demos?/", re.IGNORECASE),          # demo/ or demos/ directory
]
```

### Step 2: Add regression tests

**File**: `tests/unit/test_roadmap_sync_exclusions.py` (new)

Test cases:

- `tests/unit/test_foo.py` → excluded (test directory + test file)
- `src/contest/runner.py` → NOT excluded (contains "test" substring but not a test path)
- `src/cortex/validation/test_helper.py` → NOT excluded (production file with "test" in name but not test_ prefix)
- `src/examples/demo.py` → excluded (examples directory)
- `src/demonstration.py` → NOT excluded (contains "demo" substring)
- `test_integration.py` at root → excluded (test_ prefix)
- `src/cortex/latest_metrics.py` → NOT excluded (contains "test" substring)

### Step 3: Verify no production files were previously missed

Run the updated scanner on the full codebase and compare output with the old patterns to identify any TODOs that were previously hidden.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `_EXCLUDE_PATTERNS` | `src/cortex/validation/roadmap_sync.py` | Updated patterns with path-segment matching |
| `_is_production_file` | `src/cortex/validation/roadmap_sync.py` | Uses updated patterns |
| `test_roadmap_sync_exclusions` | `tests/` | New test file with 7+ test cases |

## Dependencies

- None.

## Success Criteria

- `_EXCLUDE_PATTERNS` use word-boundary or path-segment matching, not bare substrings.
- All 7+ regression tests pass.
- No production files with TODO comments are incorrectly excluded.
- Existing test suite passes (no regressions).

## Testing Strategy

- **Coverage Target**: 95% for modified code
- **Unit tests**: 7+ cases covering true positives and false negatives
- **Integration**: Run full roadmap sync to verify no regressions

## Risks & Mitigation

- **Risk**: New patterns might be too strict and miss some test files. **Mitigation**: Run both old and new patterns on codebase and diff results.
