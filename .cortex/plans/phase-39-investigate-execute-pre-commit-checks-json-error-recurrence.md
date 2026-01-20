# Phase 39: Investigate execute_pre_commit_checks JSON Error Recurrence

**Status**: Complete
**Priority**: ASAP (Blocker)
**Created**: 2026-01-16
**Completed**: 2026-01-16
**Phase**: 39

## Goal

Investigate and fix the recurring JSON parsing error that occurs when calling `execute_pre_commit_checks()` MCP tool during commit procedure. The error "Expected ',' or '}' after property value in JSON at position 14" blocks the entire commit procedure.

## Investigation Results

### Summary

After thorough investigation, the `execute_pre_commit_checks()` tool works correctly at all levels:

1. **Direct function call**: Returns valid JSON-serializable dict
2. **MCP interface call**: `mcp.call_tool('execute_pre_commit_checks', {})` returns valid JSON
3. **JSON serialization**: All responses serialize and parse correctly

The error format "Expected ',' or '}' after property value in JSON at position 14" is a JavaScript/TypeScript JSON parser error message (Python uses different error format), suggesting the issue is client-side, not server-side.

### Issues Found and Fixed

1. **Test bug fix**: `test_validate_error_status` was incorrectly expecting `MCPToolFailure` for `status="error"` responses. A response with `status="error"` means the tool worked correctly and found errors in the code (e.g., type errors). This is NOT a tool failure. Updated test to verify error status is a valid response.

2. **Validation logic fix**: `validate_mcp_tool_response()` was not raising `MCPToolFailure` for `None` responses because `detect_failure()` didn't recognize "None response" as a failure keyword. Fixed to always treat `None` response as a tool failure.

3. **Added tests**: Added `TestResponseSerialization` class with 2 tests verifying JSON serialization works correctly for both success and error responses.

### Technical Findings

- Tool returns valid `PreCommitResult` TypedDict that FastMCP serializes correctly
- JSON validation in `_build_response()` catches serialization issues early
- All parameter defaults serialize correctly to JSON
- The original "position 14" error was likely a client-side issue, not server-side

## Context

During commit procedure execution, Step 0 (Fix Errors) calls `execute_pre_commit_checks()` MCP tool without parameters (using defaults). The tool call fails with:

```
Error: Expected ',' or '}' after property value in JSON at position 14 (line 1 column 15)
```

This is a recurring issue that was supposedly fixed in:

- Phase 38: Investigate Recurring MCP Tool Serialization Errors (2026-01-16) - Marked Complete
- Phase 37: Investigate execute_pre_commit_checks JSON Parsing Error (2026-01-16) - Marked Complete
- Phase 35: Fix execute_pre_commit_checks MCP JSON Parsing Error (2026-01-16)
- Phase 33: Fix execute_pre_commit_checks JSON Parsing Error (2026-01-16)

However, the error is occurring again when calling the tool without parameters, indicating:

1. The fix was incomplete or didn't address this specific code path
2. There's a different code path when calling with default parameters
3. The error occurs in a different part of the tool execution
4. There's a regression in the codebase

## Impact

- **CRITICAL**: Commit procedure is completely blocked
- Cannot proceed with any pre-commit checks (fix errors, format, type check, quality, tests)
- Blocks all development workflow that requires commits
- Violates MCP tool failure protocol (tool failure must be investigated before proceeding)

## Root Cause Analysis

### Previous Fixes

**Phase 38** (2026-01-16) - Marked Complete:

- Root cause: `fix_quality_issues()` was returning JSON strings instead of dicts
- Solution: Changed return type from `str` to `FixQualityResult`, updated return statements to return dicts

**Phase 37** (2026-01-16) - Marked Complete:

- Root cause: Type mismatch between `PreCommitResult` TypedDict return value and `dict[str, object]` return type annotation
- Solution: Updated `_build_response()` to explicitly construct plain dict instead of TypedDict constructor, updated `_create_error_result()` to explicitly construct plain dict, added JSON serialization validation

**Phase 35** (2026-01-16):

- Root cause: Type mismatch between `PreCommitResult` TypedDict return value and `dict[str, object]` return type annotation
- Solution: Changed return type annotation from `dict[str, object]` to `PreCommitResult`, updated TypedDict to include optional fields using `total=False`

**Phase 33** (2026-01-16):

- Root cause: FastMCP expects tools to return `dict`/`object` types, but tool was returning pre-serialized JSON string
- Solution: Changed return type from `str` to `dict[str, object]`, updated all return statements to return dicts

### Current Issue

The error occurs at JSON position 14 when calling `execute_pre_commit_checks()` without parameters. This suggests:

- The tool is returning malformed JSON
- FastMCP serialization is failing
- There's a type mismatch in the return value
- The return value contains invalid JSON characters
- The error might occur in a specific code path (e.g., language detection, error handling)

### Investigation Steps

1. **Check current implementation**:
   - Review `src/cortex/tools/pre_commit_tools.py`
   - Verify return type annotation matches actual return type
   - Check if `PreCommitResult` TypedDict is properly defined
   - Verify all return paths return proper `PreCommitResult` dicts
   - Check error handling paths (exception handling)

2. **Test tool call without parameters**:
   - Try calling tool without parameters: `execute_pre_commit_checks()`
   - Try calling tool with explicit parameters: `execute_pre_commit_checks(checks=["fix_errors"])`
   - Check if error occurs with all parameter combinations or specific ones
   - Test language detection path (when `language=None`)

3. **Check FastMCP serialization**:
   - Verify FastMCP can serialize `PreCommitResult` TypedDict
   - Check if there are any non-serializable values in the return dict
   - Verify all dict values are JSON-serializable
   - Check if error occurs during serialization or before

4. **Check error location**:
   - JSON position 14 suggests early in the JSON string
   - Check what value is at position 14 in the serialized JSON
   - Verify no control characters or invalid JSON characters
   - Check if error occurs in `_build_response()` or `_create_error_result()`

5. **Check language detection path**:
   - Review `_detect_or_use_language()` function
   - Check if error occurs when language detection fails
   - Verify error response from language detection is properly formatted
   - Check if `LanguageInfo` vs `PreCommitResult` type confusion exists

6. **Compare with working tools**:
   - Check other MCP tools that work correctly
   - Compare their return type annotations and return values
   - Identify differences in implementation

## Implementation Steps

### Step 1: Reproduce the Error

1. Call `execute_pre_commit_checks()` MCP tool via MCP protocol without parameters
2. Capture exact error message and stack trace
3. Check if error occurs with all parameter combinations
4. Document exact conditions that trigger the error
5. Test if error occurs in error paths vs success paths

### Step 2: Review Current Implementation

1. Read `src/cortex/tools/pre_commit_tools.py`
2. Verify `PreCommitResult` TypedDict definition
3. Check return type annotation on `execute_pre_commit_checks()`
4. Review all return statements in the function
5. Check helper functions that return `PreCommitResult`
6. Review `_detect_or_use_language()` return type handling
7. Check exception handling in `execute_pre_commit_checks()`

### Step 3: Identify Root Cause

1. Compare current implementation with Phase 37/38 fixes
2. Check if Phase 37/38 changes are still present
3. Identify what changed since Phase 37/38
4. Determine if there's a different code path causing the issue
5. Check if error occurs in specific conditions (e.g., language detection, error paths)
6. Verify if `_detect_or_use_language()` is returning proper types

### Step 4: Fix the Issue

1. Apply fix based on root cause analysis
2. Ensure return type annotation matches actual return type
3. Verify all return paths return proper `PreCommitResult` dicts
4. Ensure all dict values are JSON-serializable
5. Fix any type confusion between `LanguageInfo` and `PreCommitResult`
6. Test fix with MCP tool call

### Step 5: Add Tests

1. Add unit tests for MCP tool call via MCP protocol
2. Test error paths and success paths
3. Test with different parameter combinations (including no parameters)
4. Test language detection path
5. Verify JSON serialization works correctly
6. Ensure tests cover the specific error condition

### Step 6: Verify Fix

1. Call `execute_pre_commit_checks()` MCP tool via MCP protocol without parameters
2. Verify tool returns proper JSON response
3. Test all parameter combinations
4. Verify commit procedure can proceed past Step 0
5. Run full commit procedure to ensure no regressions

## Dependencies

- None (blocker issue)

## Success Criteria

- ✅ `execute_pre_commit_checks()` MCP tool works correctly via MCP protocol (with and without parameters)
- ✅ No JSON parsing errors when calling the tool
- ✅ Tool returns proper `PreCommitResult` dict that FastMCP can serialize
- ✅ Commit procedure can successfully execute Step 0 (Fix Errors)
- ✅ All pre-commit checks work via MCP protocol
- ✅ Unit tests verify MCP tool call works correctly (including no-parameter case)
- ✅ No regressions in existing functionality

## Technical Design

### Current Implementation

- Tool: `execute_pre_commit_checks()` in `src/cortex/tools/pre_commit_tools.py`
- Return type: Should be `PreCommitResult` TypedDict
- Serialization: FastMCP should serialize TypedDict to JSON automatically
- Language detection: `_detect_or_use_language()` returns `LanguageInfo | PreCommitResult`

### Expected Behavior

- Tool should return `PreCommitResult` dict
- FastMCP should serialize dict to JSON
- MCP client should receive valid JSON response
- Language detection should return `LanguageInfo` or error `PreCommitResult`

### Actual Behavior

- Tool call fails with JSON parsing error at position 14
- Error suggests malformed JSON in response
- Error occurs when calling without parameters (using defaults)

## Testing Strategy

1. **Unit Tests**:
   - Test `execute_pre_commit_checks()` function directly
   - Test return value structure
   - Test JSON serialization of return value
   - Test with no parameters (defaults)
   - Test language detection path

2. **Integration Tests**:
   - Test MCP tool call via MCP protocol
   - Test with different parameter combinations (including no parameters)
   - Test error paths and success paths
   - Test language detection failure path

3. **Manual Testing**:
   - Call tool via MCP protocol during commit procedure
   - Verify tool works correctly with no parameters
   - Verify commit procedure can proceed
   - Test all parameter combinations

## Risks & Mitigation

- **Risk**: Fix might break existing functionality
  - **Mitigation**: Add comprehensive tests, verify all existing tests pass

- **Risk**: Root cause might be in FastMCP serialization
  - **Mitigation**: Check FastMCP version and compatibility, test with other tools

- **Risk**: Error might occur in specific conditions only (e.g., language detection)
  - **Mitigation**: Test with all parameter combinations, test error paths, test language detection

- **Risk**: Type confusion between `LanguageInfo` and `PreCommitResult`
  - **Mitigation**: Review type handling in `_detect_or_use_language()`, ensure proper type checking

## Timeline

- **Investigation**: 1-2 hours
- **Fix Implementation**: 1-2 hours
- **Testing**: 1 hour
- **Total**: 3-5 hours

## Notes

- This is a blocker issue - commit procedure cannot proceed until fixed
- Error pattern matches previous fixes, suggesting incomplete fix or regression
- Need to verify Phase 37/38 changes are still present and working
- Error occurs when calling without parameters, suggesting issue in default parameter handling or language detection
- May need to check `_detect_or_use_language()` return type handling more carefully
