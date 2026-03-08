# Add Atomic Memory Bank Writes

**Status**: PENDING
**Priority**: Medium
**Complexity**: Medium
**Category**: Fix / Reliability
**Component**: tools/files
**Work Type**: fix
**Execution Order**: 17

## Goal

Make `manage_file()` write operations atomic (temp file + rename) to prevent file truncation from interrupted writes.

## Context

- `manage_file` in `src/cortex/tools/files/crud_operations.py` already creates snapshots with version numbers. However, the write itself is not atomic — an interrupted write can leave the file truncated.
- `common-checklist.md` Phase 2.1 only blocks on empty files, not corrupted/truncated ones.
- Memory bank files (especially `roadmap.md`) are critical; a truncated roadmap blocks the entire pipeline.

## Implementation Steps

### Step 1: Implement atomic write pattern

**File**: `src/cortex/tools/files/crud_operations.py` (write operation)

Replace direct file write with:

```python
import tempfile
import os

# Write to temp file in same directory (ensures same filesystem for rename)
dir_path = file_path.parent
with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, suffix='.tmp', delete=False) as tmp:
    tmp.write(content)
    tmp.flush()
    os.fsync(tmp.fileno())
    tmp_path = Path(tmp.name)

# Atomic rename
tmp_path.rename(file_path)
```

### Step 2: Add write verification

After the atomic rename, read back the first and last 100 bytes and verify they match the written content. If mismatch, raise an error and attempt to restore from the latest snapshot.

### Step 3: Add unit tests

**File**: `tests/unit/test_atomic_writes.py` (new)

Test cases:

- Normal write succeeds and file content matches
- Write to same filesystem uses rename (not copy)
- Snapshot is created before overwrite
- Corrupted temp file does not overwrite original (simulate by making temp dir read-only)

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `NamedTemporaryFile` or `atomic` | `crud_operations.py` | Atomic write pattern |
| `fsync` | `crud_operations.py` | Flush to disk before rename |
| `test_atomic_writes` | `tests/` | Test file exists |

## Dependencies

- None.

## Success Criteria

- All `manage_file` writes use temp file + rename pattern.
- `fsync` ensures data is on disk before rename.
- Existing tests pass (no behavior change for successful writes).
- New tests cover atomic write edge cases.

## Testing Strategy

- **Coverage Target**: 95% for modified code
- **Unit tests**: 4+ test cases for atomic write behavior
