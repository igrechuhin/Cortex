# Phase 42: Investigate execute_pre_commit_checks JSON Error During Commit

**Status**: Planning  
**Priority**: FIX-ASAP (Blocker)  
**Created**: 2026-01-17  
**Related**: Phase 40, Phase 41

## Goal

Investigate and fix the JSON parsing error that occurs when calling `execute_pre_commit_checks()` MCP tool during commit procedure, blocking the entire commit pipeline.

## Context

During commit procedure execution, Step 0 (Fix Errors) failed when calling `execute_pre_commit_checks()` MCP tool with the following error:

```
Error: Expected ',' or '}' after property value in JSON at position 14 (line 1 column 15)
```

This is the same error pattern that was supposedly fixed in:

- **Phase 40**: Fixed nested TypedDict serialization by converting `CheckResult` and `TestResult` to plain dicts
- **Phase 41**: Migrated from MCP SDK FastMCP 1.0 to FastMCP 2.0 standalone package

However, the error is still occurring, indicating that either:

1. The fix in Phase 40/41 was incomplete
2. A regression was introduced
3. There's a different serialization issue not addressed by previous fixes

## Impact

**CRITICAL BLOCKER**: The commit procedure cannot proceed because Step 0 (Fix Errors) requires `execute_pre_commit_checks()` to work. This blocks all commits until resolved.

## Investigation Approach

### Step 1: Reproduce the Error

1. Attempt to call `execute_pre_commit_checks()` MCP tool directly
2. Capture the exact error message and stack trace
3. Check if error occurs with all check types or specific ones
4. Verify if error occurs with default parameters or specific parameters

### Step 2: Analyze Tool Response Structure

1. Review `pre_commit_tools.py` implementation:
   - Check `_build_response()` function for JSON serialization
   - Check `_sanitize_check_result()` and `_sanitize_test_result()` functions
   - Verify all TypedDicts are converted to plain dicts
   - Check for any remaining TypedDict instances in response

2. Review FastMCP 2.0 serialization:
   - Check if FastMCP 2.0 handles nested dicts correctly
   - Verify if there are any special serialization requirements
   - Check FastMCP 2.0 documentation for known issues

### Step 3: Check for Regression

1. Review changes made since Phase 40/41:
   - Check git history for `pre_commit_tools.py`
   - Check if any changes were made to response structure
   - Verify if any new TypedDicts were introduced

2. Test with previous working version:
   - If possible, test with code from before Phase 40/41
   - Compare response structures

### Step 4: Identify Root Cause

1. Add debug logging to capture actual response before serialization
2. Test JSON serialization manually:

   ```python
   import json
   result = execute_pre_commit_checks(...)
   json.dumps(result)  # Should this fail?
   ```

3. Check if error occurs at tool level or MCP protocol level
4. Verify if error is client-side (JSON parsing) or server-side (serialization)

### Step 5: Fix Implementation

Based on investigation findings:

1. Fix any remaining TypedDict serialization issues
2. Ensure all nested structures are plain dicts
3. Add JSON serialization validation before returning response
4. Add comprehensive tests for JSON serialization

## Technical Details

### Error Message

```
Error: Expected ',' or '}' after property value in JSON at position 14 (line 1 column 15)
```

### Affected Tool

- `execute_pre_commit_checks()` MCP tool
- Located in: `src/cortex/tools/pre_commit_tools.py`

### Previous Fixes

- **Phase 40**: Converted nested `CheckResult` and `TestResult` TypedDicts to plain dicts
- **Phase 41**: Migrated to FastMCP 2.0 standalone package

### Current Implementation

- Tool uses `PreCommitResult` TypedDict as return type
- Response building uses `_build_response()` function
- Nested results are sanitized via `_sanitize_check_result()` and `_sanitize_test_result()`

## Success Criteria

- ✅ `execute_pre_commit_checks()` MCP tool can be called without JSON parsing errors
- ✅ All pre-commit checks (fix_errors, format, type_check, quality, tests) work correctly
- ✅ Commit procedure can proceed past Step 0 (Fix Errors)
- ✅ JSON serialization validation passes for all response structures
- ✅ Comprehensive tests added to prevent regression

## Dependencies

- FastMCP 2.0 standalone package (already installed)
- MCP SDK 1.25.0 (dependency of FastMCP 2.0)

## Risks & Mitigation

- **Risk**: Fix might break existing functionality
  - **Mitigation**: Add comprehensive tests before and after fix
- **Risk**: Root cause might be in FastMCP 2.0 itself
  - **Mitigation**: Check FastMCP 2.0 issues/PRs, consider workaround if needed
- **Risk**: Multiple serialization issues might exist
  - **Mitigation**: Comprehensive review of all response structures

## Timeline

- **Investigation**: 1-2 hours
- **Fix Implementation**: 1-2 hours
- **Testing**: 1 hour
- **Total**: 3-5 hours

## Notes

- This is a critical blocker for commit procedure
- Error pattern matches previous issues, suggesting incomplete fix
- Need to verify if FastMCP 2.0 migration introduced new issues
- Consider adding JSON serialization validation to all MCP tools
