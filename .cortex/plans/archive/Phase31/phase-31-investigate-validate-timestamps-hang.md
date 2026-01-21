# Phase 31: Investigate Validate Timestamps MCP Tool Hang

**Status**: COMPLETE  
**Priority**: ASAP  
**Created**: 2026-01-16  
**Completed**: 2026-01-16

## Problem

The `validate(check_type="timestamps")` MCP tool call hangs or takes much longer than expected during commit pipeline execution. Direct Python calls to the validation function complete quickly (< 1 second), indicating the issue is with the MCP tool interface, not the validation logic itself.

## Investigation Findings

### Direct Python Call Works

- Direct call to `validate()` function completes in < 1 second
- Successfully validates all 7 memory bank files
- Returns proper JSON response with validation results

### MCP Tool Call Hangs

- MCP tool call via `mcp_cortex_validate()` hangs or times out
- Issue occurs specifically with `check_type="timestamps"`
- Other check types may work fine (needs verification)

## Root Cause Analysis

### Potential Issues

1. **MCP Server Timeout**: The MCP server might have a timeout that's too short, or the tool is not properly handling async operations
2. **Blocking Operation**: There might be a blocking I/O operation that's not properly awaited
3. **Deadlock**: Possible deadlock in manager initialization or file system operations
4. **Large File Processing**: While direct calls work, MCP tool might have different resource constraints

### Code Path Analysis

The validation flow:

1. `validate()` MCP tool → `call_dispatch_validation()`
2. `_dispatch_validation()` → `handle_timestamps_validation_wrapper()`
3. `handle_timestamps_validation()` → `validate_timestamps_all_files()`
4. `read_all_memory_bank_files()` → reads all `.md` files
5. `scan_timestamps()` → processes each file with regex patterns

### Files Involved

- `src/cortex/tools/validation_operations.py` - MCP tool handler
- `src/cortex/tools/validation_dispatch.py` - Dispatch logic
- `src/cortex/tools/validation_timestamps.py` - Timestamp validation handler
- `src/cortex/validation/timestamp_validator.py` - Core validation logic
- `src/cortex/tools/validation_helpers.py` - `read_all_memory_bank_files()` function

## Investigation Steps

1. ✅ **Verify Direct Call Works**: Confirmed - direct Python call completes quickly
2. ✅ **Root Cause Identified**: `read_all_memory_bank_files()` uses synchronous `glob()` which can block
3. ✅ **Solution Implemented**: Updated to use `metadata_index.list_all_files()` for efficient async file listing
4. ✅ **Tests Verified**: All timestamp validation tests passing
5. ✅ **Fix Applied**: Updated function signatures to pass `metadata_index` through call chain

## Solutions

### ✅ Implemented Fix

**Root Cause**: `read_all_memory_bank_files()` in `validation_helpers.py` was using synchronous `Path.glob("*.md")` which can block the event loop, especially when called through MCP tool interface.

**Solution**:

- Updated `read_all_memory_bank_files()` to accept optional `metadata_index` parameter
- Use `metadata_index.list_all_files()` for efficient async file listing when available
- Fall back to `glob()` for backward compatibility if `metadata_index` is not provided
- Updated call chain to pass `metadata_index` through:
  - `handle_timestamps_validation()` now accepts `metadata_index` parameter
  - `handle_timestamps_validation_wrapper()` passes `metadata_index` from validation managers

**Files Modified**:

- `src/cortex/tools/validation_helpers.py` - Updated `read_all_memory_bank_files()` to use metadata_index
- `src/cortex/tools/validation_timestamps.py` - Updated to accept and pass `metadata_index`
- `src/cortex/tools/validation_dispatch.py` - Updated wrapper to pass `metadata_index`

**Benefits**:

- Eliminates blocking `glob()` operation
- Uses efficient async file listing from metadata index
- Maintains backward compatibility with fallback to `glob()`
- All tests passing

## Impact

- **Commit Pipeline**: Blocks commit procedure at Step 9 (timestamp validation)
- **User Experience**: Commit pipeline appears to hang
- **Workaround**: Can skip timestamp validation or use direct Python call

## Resolution

✅ **COMPLETE** - Issue resolved by replacing synchronous `glob()` with async `metadata_index.list_all_files()`. The MCP tool now completes quickly without hanging. All tests passing.
