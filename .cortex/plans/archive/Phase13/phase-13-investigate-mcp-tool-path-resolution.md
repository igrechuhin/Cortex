# Phase 13: Investigate MCP Tool Path Resolution Issue

## Status

- **Status**: 🔴 BLOCKER - ASAP Priority
- **Priority**: Critical (Blocks proper Memory Bank operations)
- **Start Date**: 2026-01-13
- **Type**: Bug Investigation

## Problem Statement

The `manage_file` MCP tool in `src/cortex/tools/file_operations.py` has incorrect path resolution for Memory Bank files.

### Issue Details

**Current Behavior:**

- Tool looks for files in `root / "memory-bank"` (line 553)
- Tool lists available files from `root / "memory-bank"` (line 283)

**Expected Behavior:**

- Tool should look for files in `root / ".cortex" / "memory-bank"`
- This matches the actual file location and how `MetadataIndex` resolves paths

**Impact:**

- Initial read operations fail with "File does not exist" errors
- Forces fallback to direct file reading instead of using MCP tools
- Inconsistent behavior between different parts of the codebase

## Root Cause Analysis

### Code Locations

1. **`src/cortex/tools/file_operations.py`**:
   - Line 553: `memory_bank_dir = root / "memory-bank"` ❌
   - Line 283: `(root / "memory-bank").glob("*.md")` ❌

2. **`src/cortex/core/metadata_index.py`**:
   - Line 34: `self.memory_bank_dir: Path = self.cortex_dir / "memory-bank"` ✅
   - Where `cortex_dir = project_root / ".cortex"` ✅

### Inconsistency

The `MetadataIndex` correctly uses `.cortex/memory-bank/` but `file_operations.py` uses `memory-bank/` directly, causing path resolution failures.

## Investigation Tasks

### 1. Verify All Path References

- [ ] Search codebase for all references to `memory-bank` path construction
- [ ] Identify all locations using `root / "memory-bank"` instead of `root / ".cortex" / "memory-bank"`
- [ ] Check for similar issues in other MCP tools

### 2. Check for Symlink Handling

- [ ] Verify if symlinks (`.cursor/memory-bank -> ../.cortex/memory-bank`) are being used
- [ ] Determine if tool should support both symlink and direct paths
- [ ] Test path resolution with and without symlinks

### 3. Review Other MCP Tools

- [ ] Check `phase1_foundation_rollback.py` for similar path issues
- [ ] Check `phase2_linking.py` for path resolution consistency
- [ ] Review all tools that access Memory Bank files

### 4. Test Path Resolution

- [ ] Test `manage_file` tool with correct path fix
- [ ] Verify all operations (read, write, metadata) work correctly
- [ ] Test with different project root configurations
- [ ] Verify error messages for non-existent files

### 5. Fix Implementation

- [ ] Update `_validate_and_get_path()` to use `.cortex/memory-bank/`
- [ ] Update error message file listing to use correct path
- [ ] Ensure consistency with `MetadataIndex` path resolution
- [ ] Add unit tests for path resolution

### 6. Verify No Regressions

- [ ] Run full test suite
- [ ] Test Memory Bank operations end-to-end
- [ ] Verify no other tools break with path change

## Expected Outcome

- All MCP tools consistently use `.cortex/memory-bank/` for Memory Bank file paths
- `manage_file` tool works correctly for all operations
- No need to fallback to direct file reading
- Consistent path resolution across entire codebase

## Related Files

- `src/cortex/tools/file_operations.py` - Main tool implementation
- `src/cortex/core/metadata_index.py` - Reference implementation (correct)
- `src/cortex/tools/phase1_foundation_rollback.py` - May have similar issues
- `src/cortex/tools/phase2_linking.py` - May have similar issues

## Notes

- Initial fix applied: Changed `root / "memory-bank"` to `root / ".cortex" / "memory-bank"` in two locations
- Need comprehensive review to ensure no other tools have similar issues
- Consider creating a shared path resolution helper function to prevent future inconsistencies
