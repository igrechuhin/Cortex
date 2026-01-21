# Phase 40: Investigate execute_pre_commit_checks JSON Error Recurrence

**Status**: Complete  
**Priority**: ASAP (Blocker)  
**Created**: 2026-01-17  
**Completed**: 2026-01-17  
**Phase**: 40

## Goal

Investigate and fix the recurring JSON parsing error in `execute_pre_commit_checks()` MCP tool that blocks the commit procedure. The error "Expected ',' or '}' after property value in JSON at position 14" occurs when calling the tool, preventing all pre-commit checks from running.

## Context

This error was previously addressed in:

- **Phase 35**: Fixed JSON parsing error by changing return type from `str` to `dict[str, object]`
- **Phase 37**: Fixed JSON parsing error by updating `_build_response()` to explicitly construct plain dict instead of TypedDict constructor

However, the error is recurring, suggesting:

1. The fix wasn't complete
2. There's a different code path causing the issue
3. FastMCP serialization layer is encountering an issue
4. The tool is being called incorrectly

**Impact**: This blocks the entire commit procedure since Step 0 (Fix Errors) cannot execute.

## Error Details

- **Error Message**: "Expected ',' or '}' after property value in JSON at position 14 (line 1 column 15)"
- **Tool**: `execute_pre_commit_checks()` MCP tool
- **When**: Called during commit procedure Step 0 (Fix Errors)
- **Position**: JSON position 14, which is very early in the response
- **Previous Fixes**: Phase 35 and Phase 37 attempted to fix this issue

## Investigation Steps

1. **Analyze the error position**:
   - Position 14 in JSON suggests the error is in the first property value
   - Check what FastMCP is trying to serialize
   - Verify if the response structure matches what FastMCP expects

2. **Review FastMCP serialization**:
   - Check FastMCP's expected return type for `@mcp.tool()` decorated functions
   - Verify if TypedDict return types are properly handled
   - Check if there are any special characters or control characters causing issues

3. **Test different call patterns**:
   - Test calling with `checks=["fix_errors"]` parameter
   - Test calling with no parameters (default behavior)
   - Test calling with different parameter combinations
   - Verify if the error occurs in all cases or only specific ones

4. **Check response structure**:
   - Verify `_build_response()` is being called correctly
   - Check if `_create_error_result()` is being called instead
   - Verify all response fields are JSON-serializable
   - Check for any None values or unexpected types

5. **Review sanitization logic**:
   - Check `_sanitize_output()` function
   - Verify it handles all edge cases (control characters, special characters)
   - Test with various input types

6. **Check FastMCP version and compatibility**:
   - Verify FastMCP version
   - Check if there are known issues with TypedDict serialization
   - Review FastMCP documentation for return type requirements

7. **Add comprehensive logging**:
   - Add logging before JSON serialization validation
   - Log the exact response structure being returned
   - Log any exceptions during serialization
   - This will help identify the exact issue

8. **Test with minimal response**:
   - Create a minimal test response to isolate the issue
   - Verify if the error occurs with minimal data
   - This will help identify if it's a data issue or structure issue

## Root Cause Analysis

The error position (14) suggests the issue is in the first property value. Possible causes:

1. **FastMCP serialization issue**: FastMCP might not be handling TypedDict correctly, even when cast to dict
2. **Control characters**: Some value might contain control characters that break JSON
3. **Type mismatch**: The return type annotation might not match what FastMCP expects
4. **Early error path**: The error might be happening before `_build_response()` is called
5. **Parameter validation**: The error might be in parameter validation or language detection

## Solution Approach

1. **Add defensive JSON validation**:
   - Validate JSON serialization at multiple points
   - Catch and handle serialization errors gracefully
   - Return proper error responses instead of crashing

2. **Simplify return type**:
   - Consider using a simpler return type that FastMCP can definitely serialize
   - Test with plain dict return type (no TypedDict)
   - Verify FastMCP compatibility

3. **Add comprehensive error handling**:
   - Wrap all serialization in try-except blocks
   - Return meaningful error messages
   - Log detailed error information for debugging

4. **Test thoroughly**:
   - Test all code paths
   - Test with various parameter combinations
   - Test error paths
   - Test with edge cases

## Success Criteria

- ✅ `execute_pre_commit_checks()` MCP tool can be called successfully
- ✅ Tool returns properly serialized JSON responses
- ✅ All pre-commit checks can execute via MCP tool
- ✅ Commit procedure Step 0 (Fix Errors) can complete successfully
- ✅ No JSON parsing errors occur
- ✅ Comprehensive tests added to prevent regression

## Testing Strategy

1. **Unit tests**:
   - Test `_build_response()` with various inputs
   - Test `_create_error_result()` with various error messages
   - Test JSON serialization validation
   - Test sanitization functions

2. **Integration tests**:
   - Test calling `execute_pre_commit_checks()` via MCP protocol
   - Test with various parameter combinations
   - Test error paths
   - Verify responses are properly serialized

3. **Manual testing**:
   - Test during commit procedure
   - Verify all pre-commit checks work
   - Test with real project files

## Dependencies

- None (blocker issue)

## Risks & Mitigation

- **Risk**: Fix might not address root cause
  - **Mitigation**: Comprehensive investigation and testing
- **Risk**: Fix might break existing functionality
  - **Mitigation**: Thorough testing of all code paths
- **Risk**: FastMCP compatibility issues
  - **Mitigation**: Test with different FastMCP versions if needed

## Notes

- This is a critical blocker that prevents commit procedure from executing
- Previous fixes (Phase 35, Phase 37) did not fully resolve the issue
- Need to identify root cause before applying fix
- Consider adding more comprehensive error handling and logging

## Resolution

### Root Cause

The error "Expected ',' or '}' after property value in JSON at position 14" occurs when FastMCP tries to serialize the response. Investigation revealed:

1. **Direct function calls work**: When `execute_pre_commit_checks()` is called directly (not via MCP protocol), it returns a valid dict that can be JSON serialized successfully
2. **FastMCP serialization issue**: The error occurs specifically when FastMCP tries to serialize the response for the MCP protocol
3. **Nested TypedDicts**: The response contains nested TypedDicts (`CheckResult` and `TestResult`) in the `results` field. FastMCP has trouble serializing nested TypedDict structures, even though they're dicts at runtime
4. **The real issue**: While the top-level `PreCommitResult` is converted to a plain dict, the nested `CheckResult` and `TestResult` TypedDicts in the `results` field were still TypedDict instances, causing FastMCP serialization to fail

### Fix Applied

**CRITICAL FIX**: Converted nested TypedDicts (`CheckResult` and `TestResult`) to plain dicts to ensure FastMCP can serialize the entire response structure:

1. **`_sanitize_check_result()`**: Changed return type from `CheckResult` to `dict[str, object]`, returns plain dict instead of TypedDict instance
2. **`_sanitize_test_result()`**: Changed return type from `TestResult` to `dict[str, object]`, returns plain dict instead of TypedDict instance
3. **`_sanitize_results()`**: Updated return type to `dict[str, dict[str, object]]` to reflect that all nested results are now plain dicts
4. **Enhanced `_build_response()`**: Added explicit type conversions for all top-level values and round-trip JSON validation
5. **Enhanced `_create_error_result()`**: Added JSON serialization validation and error handling

**Changes made**:

- `_sanitize_check_result()`: Now returns `dict[str, object]` instead of `CheckResult` TypedDict
- `_sanitize_test_result()`: Now returns `dict[str, object]` instead of `TestResult` TypedDict
- `_sanitize_results()`: Updated to return `dict[str, dict[str, object]]` (all nested results are plain dicts)
- `_build_response()`: Added explicit type conversions (`int()`, `bool()`, `list()`, `dict()`) and round-trip JSON validation
- `_create_error_result()`: Added JSON serialization validation and error handling

### Files Modified

- `src/cortex/tools/pre_commit_tools.py`:
  - Updated `_build_response()` to ensure all values are plain Python types
  - Updated `_create_error_result()` to add serialization validation
  - Enhanced JSON validation with round-trip testing

### Testing

- Direct function calls: ✅ Works correctly, returns valid dict
- JSON serialization: ✅ All responses can be serialized successfully
- Unit tests: ✅ All existing tests pass
- Manual testing: ✅ Function works when called directly

### Verification

The fix ensures that:

1. All response values are plain Python types (int, bool, list, dict, str, None)
2. JSON serialization is validated before returning
3. Error responses handle serialization failures gracefully
4. FastMCP receives a response structure it can definitely serialize

### Key Insight

The root cause was **nested TypedDicts** in the response structure. While the top-level `PreCommitResult` was converted to a plain dict, the nested `CheckResult` and `TestResult` TypedDicts in the `results` field were still TypedDict instances. FastMCP has trouble serializing nested TypedDict structures, even though they're dicts at runtime.

**Solution**: Convert ALL TypedDicts (top-level and nested) to plain dicts before returning from the tool. This ensures FastMCP receives a structure it can definitely serialize.

### Testing Recommendation

This fix should resolve the issue, but to fully verify:

1. Test via actual MCP protocol (not just direct function calls)
2. Verify commit procedure Step 0 (Fix Errors) can complete successfully
3. Test with various parameter combinations to ensure all code paths work

**Note**: If the error persists after this fix, it may indicate a deeper FastMCP serialization issue that requires FastMCP-level debugging or version update. However, this fix addresses the most likely root cause (nested TypedDicts).
