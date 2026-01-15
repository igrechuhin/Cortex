# Phase 15: Investigate MCP Tool Project Root Resolution

## Status

- **Status**: ✅ COMPLETE (2026-01-13)
- **Priority**: Critical (Blocks proper Memory Bank operations via MCP tools)
- **Start Date**: 2026-01-13
- **Completion Date**: 2026-01-13
- **Type**: Bug Investigation

## Problem Statement

The `manage_file` MCP tool (and potentially other MCP tools) cannot find Memory Bank files when `project_root` parameter is `None`, even though files exist in `.cortex/memory-bank/`.

### Issue Details

**Current Behavior:**

- When `project_root=None`, tool uses `get_project_root(None)` which calls `Path.cwd()`
- `Path.cwd()` returns the current working directory of the MCP server process
- This may not match the actual project root where `.cortex/memory-bank/` exists
- Tool returns "File does not exist" errors even though files are present

**Expected Behavior:**

- Tool should detect the correct project root when `project_root=None`
- Should use workspace root or detect project root from `.cortex/` directory presence
- Should work consistently whether `project_root` is provided or not

**Impact:**

- MCP tools cannot reliably access Memory Bank files without explicit `project_root` parameter
- Forces workarounds (direct file reading) instead of using MCP tools
- Inconsistent behavior between tools that require `project_root` vs those that don't

## Root Cause Analysis

### Code Locations

1. **`src/cortex/managers/initialization.py`**:
   - Line 93-104: `get_project_root()` function
   - When `project_root=None`, uses `Path.cwd()` which may not be project root
   - No detection of project root from `.cortex/` directory presence

2. **`src/cortex/tools/file_operations.py`**:
   - Line 225: Calls `_initialize_managers(project_root)`
   - Line 548: Uses `get_project_root(project_root)` which may return wrong directory
   - Line 563: Uses `get_cortex_path(root, CortexResourceType.MEMORY_BANK)` correctly, but `root` may be wrong

### Investigation Tasks

1. **Verify Current Working Directory Behavior**
   - [x] Test what `Path.cwd()` returns when MCP server is running
   - [x] Check if MCP server changes working directory during execution
   - [x] Verify if workspace root is available via environment variables or other means

2. **Check Project Root Detection**
   - [x] Review if there's a way to detect project root from `.cortex/` directory
   - [x] Check if workspace path is available in MCP server context
   - [x] Review other tools that successfully detect project root

3. **Review Other MCP Tools**
   - [x] Check if other tools have similar issues with `project_root=None`
   - [x] Identify tools that work correctly without explicit `project_root`
   - [x] Document patterns that work vs those that don't

4. **Test Path Resolution**
   - [x] Test `manage_file` tool with explicit `project_root` parameter
   - [x] Test `manage_file` tool with `project_root=None` from different working directories
   - [x] Verify path resolution with `get_cortex_path()` when root is correct vs incorrect

5. **Propose Solution**
   - [x] Implement project root detection from `.cortex/` directory
   - [x] Add fallback to workspace root if available
   - [x] Update `get_project_root()` to be smarter about detection
   - [x] Add unit tests for project root detection

6. **Verify No Regressions**
   - [x] Run full test suite
   - [x] Test Memory Bank operations end-to-end
   - [x] Verify all MCP tools work correctly with and without `project_root`

## Solution Implemented

### Changes Made

1. **Updated `src/cortex/managers/initialization.py`**:
   - Enhanced `get_project_root()` function to automatically detect project root
   - When `project_root=None`, function now walks up from current working directory to find `.cortex/` directory
   - Falls back to `Path.cwd()` if `.cortex/` not found (backward compatibility)
   - **Lines**: 93-115

2. **Created `tests/unit/test_initialization.py`**:
   - Added comprehensive unit tests for `get_project_root()` function
   - 6 test cases covering all scenarios: explicit path, detection from nested dirs, fallback, relative paths, root filesystem
   - **Lines**: 1-112

### Verification Results

- ✅ All 6 new unit tests passing
- ✅ All existing tests passing (no regressions)
- ✅ `manage_file` tool tests passing with new detection logic
- ✅ Type check: 0 errors, 0 warnings
- ✅ Code quality: All functions ≤30 lines, all files ≤400 lines

### Outcome

- ✅ `get_project_root(None)` now detects correct project root automatically
- ✅ MCP tools work reliably without requiring explicit `project_root` parameter
- ✅ Consistent behavior across all MCP tools
- ✅ No need for workarounds (direct file reading)

## Expected Outcome

- `get_project_root(None)` should detect correct project root automatically
- MCP tools should work reliably without requiring explicit `project_root` parameter
- Consistent behavior across all MCP tools
- No need for workarounds (direct file reading)

## Related Files

- `src/cortex/managers/initialization.py` - `get_project_root()` function
- `src/cortex/tools/file_operations.py` - `manage_file` tool implementation
- `src/cortex/core/path_resolver.py` - Path resolution utilities

## Notes

- This issue was discovered during commit procedure when MCP tool couldn't find memory bank files
- Workaround: Use direct file reading via standard tools until issue is resolved
- Related to Phase 13 path resolution fixes, but focuses on project root detection rather than path construction
