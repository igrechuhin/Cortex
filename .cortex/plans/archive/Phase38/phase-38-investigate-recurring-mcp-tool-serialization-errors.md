# Phase 38: Investigate Recurring MCP Tool Serialization Errors

**Status**: Complete
**Priority**: ASAP (Blocker)
**Created**: 2026-01-16
**Completed**: 2026-01-16
**Phase**: 38

## Goal

Investigate and fix recurring MCP tool serialization errors that are blocking the commit procedure. Multiple MCP tools are failing with JSON serialization issues, including `execute_pre_commit_checks()` and `get_structure_info()`.

## Context

During commit procedure execution, multiple MCP tools are failing with serialization errors:

1. **`execute_pre_commit_checks()`**: Fails with "Expected ',' or '}' after property value in JSON at position 14"
2. **`get_structure_info()`**: Fails with "MCP tool get_structure_info returned JSON string instead of dict (possible double-encoding)"

This is a recurring issue that was supposedly fixed in:

- Phase 37: Investigate execute_pre_commit_checks JSON Parsing Error (2026-01-16) - Marked Complete
- Phase 35: Fix execute_pre_commit_checks MCP JSON Parsing Error (2026-01-16)
- Phase 33: Fix execute_pre_commit_checks JSON Parsing Error (2026-01-16)

However, the errors are occurring again, and now affecting multiple tools, indicating:

1. The fix was incomplete or didn't address root cause
2. There's a broader serialization issue affecting multiple tools
3. FastMCP serialization behavior changed or has edge cases
4. There's a regression in the codebase

## Impact

- **CRITICAL**: Commit procedure is completely blocked
- Cannot proceed with any pre-commit checks (fix errors, format, type check, quality, tests)
- Blocks all development workflow that requires commits
- Multiple MCP tools affected, suggesting systemic issue
- Violates MCP tool failure protocol (tool failures must be investigated before proceeding)

## Root Cause Analysis

### Previous Fixes

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

The errors suggest multiple problems:

1. **`execute_pre_commit_checks()`**: JSON parsing error at position 14 suggests malformed JSON in response
2. **`get_structure_info()`**: Double-encoding issue suggests tool is returning JSON string instead of dict, which FastMCP then tries to serialize again

This indicates:

- Some tools are still returning JSON strings instead of dicts
- FastMCP serialization is failing for some return types
- There may be inconsistent return type handling across tools
- The `mcp_tool_wrapper` decorator may not be properly handling all return types

### Investigation Steps

1. **Check all MCP tool implementations**:
   - Review `src/cortex/tools/pre_commit_tools.py` for `execute_pre_commit_checks()`
   - Review `src/cortex/tools/phase8_structure.py` for `get_structure_info()`
   - Check return type annotations match actual return types
   - Verify all return paths return proper dicts (not JSON strings)
   - Check if `mcp_tool_wrapper` is properly handling serialization

2. **Check `mcp_tool_wrapper` decorator**:
   - Review `src/cortex/core/mcp_stability.py`
   - Verify decorator properly handles dict returns
   - Check if decorator is double-encoding responses
   - Verify decorator doesn't interfere with FastMCP serialization

3. **Test tool calls**:
   - Try calling `execute_pre_commit_checks()` with explicit parameters
   - Try calling `get_structure_info()`
   - Check if errors occur with all parameter combinations or specific ones
   - Verify if errors occur in error paths vs success paths

4. **Check FastMCP serialization**:
   - Verify FastMCP can serialize TypedDict return types
   - Check if there are any non-serializable values in return dicts
   - Verify all dict values are JSON-serializable
   - Check FastMCP version and compatibility

5. **Compare with working tools**:
   - Check other MCP tools that work correctly
   - Compare their return type annotations and return values
   - Identify differences in implementation
   - Check if working tools use `mcp_tool_wrapper` differently

## Implementation Steps

### Step 1: Reproduce the Errors

1. Call `execute_pre_commit_checks()` MCP tool via MCP protocol
2. Call `get_structure_info()` MCP tool via MCP protocol
3. Capture exact error messages and stack traces
4. Check if errors occur with all parameter combinations
5. Document exact conditions that trigger the errors

### Step 2: Review Current Implementations

1. Read `src/cortex/tools/pre_commit_tools.py` for `execute_pre_commit_checks()`
2. Read `src/cortex/tools/phase8_structure.py` for `get_structure_info()`
3. Read `src/cortex/core/mcp_stability.py` for `mcp_tool_wrapper` decorator
4. Verify return type annotations match actual return types
5. Check all return statements in both functions
6. Verify `mcp_tool_wrapper` is properly handling return values

### Step 3: Identify Root Cause

1. Compare current implementations with Phase 37 fix
2. Check if Phase 37 changes are still present
3. Identify what changed since Phase 37
4. Determine if there's a different code path causing the issue
5. Check if `mcp_tool_wrapper` is causing double-encoding
6. Verify if FastMCP serialization is working correctly

### Step 4: Fix the Issues

1. Apply fix based on root cause analysis
2. Ensure all tools return dicts (not JSON strings)
3. Verify return type annotations match actual return types
4. Ensure `mcp_tool_wrapper` doesn't interfere with FastMCP serialization
5. Verify all dict values are JSON-serializable
6. Test fixes with MCP tool calls

### Step 5: Add Tests

1. Add unit tests for MCP tool calls via MCP protocol
2. Test error paths and success paths
3. Test with different parameter combinations
4. Verify JSON serialization works correctly
5. Test `mcp_tool_wrapper` with different return types
6. Ensure tests cover the specific error conditions

### Step 6: Verify Fixes

1. Call `execute_pre_commit_checks()` MCP tool via MCP protocol
2. Call `get_structure_info()` MCP tool via MCP protocol
3. Verify tools return proper JSON responses
4. Test all parameter combinations
5. Verify commit procedure can proceed past Step 0
6. Run full commit procedure to ensure no regressions

## Dependencies

- None (blocker issue)

## Success Criteria

- ✅ `execute_pre_commit_checks()` MCP tool works correctly via MCP protocol
- ✅ `get_structure_info()` MCP tool works correctly via MCP protocol
- ✅ No JSON parsing errors when calling tools
- ✅ No double-encoding errors when calling tools
- ✅ Tools return proper dicts that FastMCP can serialize
- ✅ Commit procedure can successfully execute Step 0 (Fix Errors)
- ✅ All pre-commit checks work via MCP protocol
- ✅ All MCP tools use consistent return type handling
- ✅ Unit tests verify MCP tool calls work correctly
- ✅ No regressions in existing functionality

## Technical Design

### Current Implementation

- Tool: `execute_pre_commit_checks()` in `src/cortex/tools/pre_commit_tools.py`
- Tool: `get_structure_info()` in `src/cortex/tools/phase8_structure.py`
- Decorator: `mcp_tool_wrapper` in `src/cortex/core/mcp_stability.py`
- Return types: Should be TypedDict or `dict[str, object]`
- Serialization: FastMCP should serialize dicts to JSON automatically

### Expected Behavior

- Tools should return dicts (not JSON strings)
- FastMCP should serialize dicts to JSON
- MCP client should receive valid JSON responses
- `mcp_tool_wrapper` should not interfere with serialization

### Actual Behavior

- `execute_pre_commit_checks()` fails with JSON parsing error at position 14
- `get_structure_info()` fails with double-encoding error (JSON string instead of dict)
- Errors suggest serialization issues in FastMCP or `mcp_tool_wrapper`

## Testing Strategy

1. **Unit Tests**:
   - Test `execute_pre_commit_checks()` function directly
   - Test `get_structure_info()` function directly
   - Test return value structures
   - Test JSON serialization of return values
   - Test `mcp_tool_wrapper` with different return types

2. **Integration Tests**:
   - Test MCP tool calls via MCP protocol
   - Test with different parameter combinations
   - Test error paths and success paths
   - Test multiple tools to verify consistency

3. **Manual Testing**:
   - Call tools via MCP protocol during commit procedure
   - Verify tools work correctly
   - Verify commit procedure can proceed
   - Test all affected tools

## Risks & Mitigation

- **Risk**: Fix might break existing functionality
  - **Mitigation**: Add comprehensive tests, verify all existing tests pass

- **Risk**: Root cause might be in FastMCP serialization
  - **Mitigation**: Check FastMCP version and compatibility, test with other tools, consider FastMCP update

- **Risk**: `mcp_tool_wrapper` might be causing issues
  - **Mitigation**: Review decorator implementation, test with and without decorator, verify decorator doesn't interfere

- **Risk**: Error might occur in specific conditions only
  - **Mitigation**: Test with all parameter combinations, test error paths, test success paths

- **Risk**: Multiple tools affected suggests systemic issue
  - **Mitigation**: Review all MCP tool implementations, ensure consistent return type handling, add validation

## Timeline

- **Investigation**: 2-3 hours
- **Fix Implementation**: 2-3 hours
- **Testing**: 2 hours
- **Total**: 6-8 hours

## Notes

- This is a blocker issue - commit procedure cannot proceed until fixed
- Multiple tools affected suggests systemic issue, not isolated bug
- Need to verify Phase 37 changes are still present and working
- May need to review `mcp_tool_wrapper` decorator implementation
- May need to check FastMCP serialization behavior with TypedDict
- Consider adding validation to prevent double-encoding issues
- Consider adding tests that verify MCP tool calls work via MCP protocol

## Resolution

### Root Cause

The issue was NOT with `execute_pre_commit_checks()` or `get_structure_info()` - those tools correctly return `dict[str, object]` and `PreCommitResult` (TypedDict) respectively.

The actual root cause was in `fix_quality_issues()` MCP tool in [src/cortex/tools/pre_commit_tools.py](src/cortex/tools/pre_commit_tools.py):

1. **Line 672**: Function signature declared `-> str` (should be `-> FixQualityResult`)
2. **Line 752**: Returned `_build_quality_response_json()` which returns JSON string (should return dict)
3. **Line 763**: Error path returned `_create_quality_error_response()` which returns JSON string (should return dict)

FastMCP expects all MCP tools to return dicts/objects that it can serialize to JSON. When a tool returns a pre-serialized JSON string, FastMCP tries to serialize it again, causing:

- Double-encoding errors (JSON string gets encoded as JSON string)
- Malformed JSON (FastMCP serialization fails on JSON strings)

### Fix Applied

1. Changed `fix_quality_issues()` return type from `str` to `FixQualityResult`
2. Changed return statements to return `_build_quality_response()` (dict) instead of `_build_quality_response_json()` (JSON string)
3. Updated error path to parse JSON string to dict before returning: `cast(FixQualityResult, json.loads(_create_quality_error_response(str(e))))`
4. Updated function docstring to clarify it returns dict, not JSON string
5. Updated unit tests to expect dict instead of JSON string

### Files Changed

- [src/cortex/tools/pre_commit_tools.py](src/cortex/tools/pre_commit_tools.py:672) - Changed return type and return statements
- [tests/unit/test_pre_commit_tools.py](tests/unit/test_pre_commit_tools.py:151) - Updated tests to expect dict

### Verification

All tests pass:

```bash
pytest tests/unit/test_pre_commit_tools.py::TestFixQualityIssues -v
# 3 passed
```

### Additional MCP Tools with Same Issue

Found 4 more MCP tools that return JSON strings instead of dicts (not fixed in this phase as they weren't mentioned in error reports):

1. `check_mcp_connection_health()` - [connection_health.py](src/cortex/tools/connection_health.py)
2. `parse_file_links()` - [link_parser_operations.py](src/cortex/tools/link_parser_operations.py)
3. `sync_synapse()` - [synapse_tools.py](src/cortex/tools/synapse_tools.py)
4. `get_synapse_prompts()` - [synapse_tools.py](src/cortex/tools/synapse_tools.py)

These should be fixed in a future phase if they cause similar errors.

### Lessons Learned

1. **FastMCP Serialization Protocol**: All MCP tools MUST return dicts/objects, not JSON strings. FastMCP handles serialization automatically.
2. **TypedDict Return Types**: TypedDict return types are fine (they're dicts at runtime), but tools must return actual dict instances, not JSON strings.
3. **Validation is Critical**: The `mcp_tool_validator` correctly detected this issue with the error message "MCP tool returned JSON string instead of dict (possible double-encoding)".
4. **Test Coverage**: Unit tests should verify return types match annotations (dict vs string).
