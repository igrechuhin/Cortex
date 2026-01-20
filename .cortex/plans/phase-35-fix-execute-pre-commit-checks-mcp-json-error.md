# Phase 35: Fix execute_pre_commit_checks MCP JSON Parsing Error

**Status**: PLANNING  
**Priority**: ASAP (Blocker)  
**Created**: 2026-01-16  
**Target Completion**: 2026-01-16

## Goal

Fix the JSON parsing error that occurs when calling `execute_pre_commit_checks()` MCP tool via MCP protocol, which blocks the commit procedure.

## Context

During commit procedure execution, the `execute_pre_commit_checks()` MCP tool fails with:

```
Error: Expected ',' or '}' after property value in JSON at position 14 (line 1 column 15)
```

This error occurs when the tool is called via MCP protocol, but the tool works correctly when called directly via Python (as shown by the direct Python call that successfully executed and returned results).

**Impact**:

- Commit procedure is completely blocked at Step 0 (Fix Errors)
- Cannot proceed with any pre-commit checks
- This is a critical blocker for all commits

## Root Cause Analysis

### Observations

1. **Direct Python call succeeds**: When calling the function directly via Python (`asyncio.run(execute_pre_commit_checks(...))`), it executes successfully and returns a valid dict structure.

2. **MCP protocol call fails**: When called via MCP protocol (`mcp_cortex_execute_pre_commit_checks`), it fails with JSON parsing error at position 14.

3. **Error location**: The error "Expected ',' or '}' after property value in JSON at position 14" suggests:
   - The response is being double-encoded (JSON string inside JSON)
   - There's a serialization issue in the MCP tool wrapper
   - The return value format doesn't match what FastMCP expects

4. **Previous fix**: Phase 33 fixed a similar issue where `execute_pre_commit_checks` was returning pre-serialized JSON strings instead of dicts. The fix changed the return type from `str` to `dict[str, object]`.

5. **Current return type**: The function signature shows:

   ```python
   async def execute_pre_commit_checks(...) -> dict[str, object]:
   ```

6. **Type mismatch**: The function returns `PreCommitResult` TypedDict (line 432), but the return type annotation is `dict[str, object]`. Pyright reports:
   - Line 432:12 - error: Type "PreCommitResult" cannot be assigned to return type "dict[str, object]"

### Hypothesis

The issue is likely one of:

1. **Double JSON encoding**: The response is being JSON-encoded twice (once by the function, once by FastMCP)
2. **Type mismatch causing serialization issues**: The `PreCommitResult` TypedDict vs `dict[str, object]` mismatch might cause FastMCP to handle it incorrectly
3. **MCP wrapper issue**: The `@mcp_tool_wrapper` decorator might be interfering with serialization
4. **Response structure issue**: The response structure might contain values that can't be properly serialized by FastMCP

## Investigation Steps

1. **Examine MCP tool registration**:
   - Check how `execute_pre_commit_checks` is registered with FastMCP
   - Verify the `@mcp.tool()` decorator configuration
   - Check if `@mcp_tool_wrapper` is interfering

2. **Examine return value structure**:
   - Review the `PreCommitResult` TypedDict structure
   - Check if all values are JSON-serializable
   - Verify nested structures (e.g., `results` dict containing `CheckResult | TestResult`)

3. **Test MCP serialization**:
   - Create a minimal test that calls the tool via MCP protocol
   - Capture the exact response before it's sent to the client
   - Compare with the direct Python call response

4. **Check FastMCP serialization**:
   - Review FastMCP's serialization behavior for TypedDict vs dict
   - Check if there are known issues with complex nested structures
   - Verify if `dict[str, object]` annotation causes issues

5. **Examine error location**:
   - Position 14 in JSON suggests the error is early in the response
   - Check the first few fields of `PreCommitResult` for serialization issues

## Implementation Steps

1. **Fix type annotation**:
   - Change return type from `dict[str, object]` to `PreCommitResult`
   - Update all call sites if needed
   - Verify type checker passes

2. **Fix serialization**:
   - Ensure all values in `PreCommitResult` are JSON-serializable
   - Check nested structures (`results`, `CheckResult`, `TestResult`)
   - Convert any non-serializable types (e.g., Path objects) to strings

3. **Test MCP protocol**:
   - Create integration test that calls tool via MCP
   - Verify response is valid JSON
   - Ensure no double-encoding occurs

4. **Verify commit procedure**:
   - Test that commit procedure can successfully call the tool
   - Verify all pre-commit checks work via MCP
   - Ensure no regressions

## Success Criteria

- ✅ `execute_pre_commit_checks()` MCP tool works correctly via MCP protocol
- ✅ No JSON parsing errors when calling the tool
- ✅ Commit procedure can successfully execute Step 0 (Fix Errors)
- ✅ All pre-commit checks work via MCP (no fallback needed)
- ✅ Type checker passes with correct return type
- ✅ All existing tests pass
- ✅ Integration test verifies MCP protocol works

## Dependencies

- None (this is a blocker that must be fixed first)

## Risks & Mitigation

- **Risk**: Fix might break direct Python calls
  - **Mitigation**: Test both MCP and direct Python calls
- **Risk**: Type changes might require updates to callers
  - **Mitigation**: Check all call sites, update if needed
- **Risk**: Complex nested structures might have serialization issues
  - **Mitigation**: Test thoroughly, convert non-serializable types

## Notes

- This is a critical blocker - commit procedure cannot proceed until fixed
- The tool works when called directly, so the issue is MCP protocol-specific
- Previous fix (Phase 33) addressed similar issue but may have introduced this one
- Need to ensure both MCP protocol and direct Python calls work
