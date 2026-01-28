# Phase 33: Fix execute_pre_commit_checks JSON Parsing Error

## Status

- **Status**: PLANNING
- **Priority**: ASAP (BLOCKER)
- **Start Date**: 2026-01-16
- **Target Completion**: 2026-01-16

## Goal

Fix the JSON parsing error that occurs when calling `execute_pre_commit_checks` MCP tool via MCP protocol, blocking the commit procedure.

## Problem Statement

The `execute_pre_commit_checks` MCP tool fails with a JSON parsing error when called via MCP protocol:

```text
Error: Expected ',' or '}' after property value in JSON at position 14 (line 1 column 15)
```

However, the tool works correctly when called directly via Python:

```python
result = asyncio.run(execute_pre_commit_checks(checks=['fix_errors'], strict_mode=False))
# Returns valid JSON string successfully
```

**Impact**: This blocks the commit procedure, forcing fallback to terminal commands instead of using the MCP tool directly.

## Root Cause Analysis

### Hypothesis 1: FastMCP Double-Encoding Issue

**Theory**: FastMCP expects tools to return `dict`/`object` types that it serializes to JSON. When a tool returns a pre-serialized JSON string, FastMCP tries to serialize it again, causing double-encoding or invalid JSON.

**Evidence**:

- Tool returns `str` (JSON string) via `json.dumps()`
- FastMCP likely serializes tool responses automatically
- Error occurs at JSON parsing stage (position 14 suggests early in response)

**Investigation Steps**:

1. Check FastMCP documentation/source for how it handles string return types
2. Compare with other MCP tools that return strings vs dicts
3. Test if changing return type to `dict` fixes the issue

### Hypothesis 2: Invalid JSON in Response

**Theory**: The JSON string returned by `_build_response()` contains invalid characters or structure that breaks JSON parsing.

**Evidence**:

- Error message indicates JSON parsing failure
- Position 14 suggests issue early in response
- Tool works when called directly (suggests response is valid)

**Investigation Steps**:

1. Inspect actual JSON string returned by `_build_response()`
2. Check for special characters, unescaped quotes, or invalid structure
3. Validate JSON using `json.loads()` before returning

### Hypothesis 3: MCP Server Response Wrapping Issue

**Theory**: The MCP server wraps tool responses in additional JSON structure, and the double-wrapping causes parsing errors.

**Evidence**:

- Error occurs during MCP protocol handling, not in tool execution
- Tool execution succeeds (returns valid JSON)
- Error happens when MCP server processes response

**Investigation Steps**:

1. Check MCP server response wrapping logic
2. Inspect actual MCP protocol messages (request/response)
3. Compare with working MCP tools to identify differences

## Context

### Related Issues

- **Phase 32: Fix MCP Tool Connection Closure Errors** - Recently fixed connection stability issues
- **Phase 31: Fix optimize_context Stale File Errors** - Fixed similar MCP tool errors
- **Phase 12: Convert Commit Workflow Prompts to MCP Tools** - Tool was created as part of this phase

### Current Implementation

**Tool Definition** (`src/cortex/tools/pre_commit_tools.py`):

```python
@mcp.tool()
async def execute_pre_commit_checks(
    checks: Sequence[str] | None = None,
    language: str | None = None,
    project_root: str | None = None,
    timeout: int | None = None,
    coverage_threshold: float = 0.90,
    strict_mode: bool = False,
) -> str:  # Returns JSON string
    """Execute pre-commit checks with language auto-detection."""
    # ... implementation ...
    return _build_response(results, stats, language_info["language"])

def _build_response(...) -> str:
    """Build JSON response."""
    response: PreCommitResult = {...}
    return json.dumps(response, indent=2)  # Returns JSON string
```

**Comparison with Other Tools**:

- `check_mcp_connection_health()` - Returns `str` (JSON string) - **Check if this works via MCP**
- `fix_markdown_lint()` - Returns `str` (JSON string) - **Check if this works via MCP**
- Other tools that return `dict` instead of `str`

## Implementation Steps

### Step 1: Investigate FastMCP String Return Type Handling

1. **Check FastMCP documentation/source**:
   - Review FastMCP source code for how it handles tool return types
   - Check if string return types are supported or if dict is required
   - Look for examples of tools returning strings vs dicts

2. **Compare with working tools**:
   - Test `check_mcp_connection_health()` via MCP to see if it works
   - Test `fix_markdown_lint()` via MCP to see if it works
   - Identify pattern: which tools work with string returns, which don't

3. **Test hypothesis**:
   - Temporarily change `execute_pre_commit_checks` to return `dict` instead of `str`
   - Test if MCP call works with dict return type
   - If successful, this confirms Hypothesis 1

### Step 2: Inspect Actual JSON Response

1. **Add logging**:
   - Log the JSON string returned by `_build_response()`
   - Log the JSON string at position 14 to see what character causes the error
   - Verify JSON is valid using `json.loads()` before returning

2. **Validate JSON structure**:
   - Check for unescaped quotes, special characters, or invalid structure
   - Ensure all values are JSON-serializable (no custom objects)
   - Verify TypedDict structure matches actual response

3. **Test with minimal response**:
   - Create minimal test response to isolate the issue
   - Gradually add fields to identify which field causes the problem

### Step 3: Check MCP Server Response Wrapping

1. **Inspect MCP protocol messages**:
   - Enable MCP server logging to see actual request/response messages
   - Check if server wraps tool responses in additional JSON structure
   - Compare request/response format with working tools

2. **Check response format**:
   - Verify MCP server expects `dict` in response, not pre-serialized JSON string
   - Check if FastMCP automatically serializes dict responses
   - Identify if string responses need special handling

### Step 4: Implement Fix

#### Option A: Change Return Type to Dict (Preferred if Hypothesis 1 is correct)

1. **Modify tool signature**:

   ```python
   @mcp.tool()
   async def execute_pre_commit_checks(...) -> dict[str, object]:  # Change from str to dict
       """Execute pre-commit checks with language auto-detection."""
       # ... implementation ...
       return _build_response_dict(results, stats, language_info["language"])  # Return dict
   ```

2. **Update response builder**:

   ```python
   def _build_response_dict(...) -> dict[str, object]:
       """Build response as dict (not JSON string)."""
       response: PreCommitResult = {...}
       return response  # Return dict, not json.dumps()
   ```

3. **Update error handler**:

   ```python
   def _create_error_result_dict(error: str, error_type: str = "ValueError") -> dict[str, object]:
       """Create error response as dict."""
       return {"status": "error", "error": error, "error_type": error_type}
   ```

4. **Update all return statements**:
   - Change all `_create_error_result()` calls to return dicts
   - Update `_build_response()` to return dict
   - Ensure FastMCP handles dict serialization

#### Option B: Fix JSON String Format (If Hypothesis 2 is correct)

1. **Validate JSON before returning**:

   ```python
   def _build_response(...) -> str:
       """Build JSON response."""
       response: PreCommitResult = {...}
       json_str = json.dumps(response, indent=2)
       # Validate JSON before returning
       json.loads(json_str)  # Raises if invalid
       return json_str
   ```

2. **Fix any invalid characters**:
   - Escape special characters properly
   - Ensure all values are JSON-serializable
   - Fix any TypedDict mismatches

#### Option C: Custom Response Handling (If Hypothesis 3 is correct)

1. **Implement custom response wrapper**:
   - Check if FastMCP supports custom response serialization
   - Implement wrapper that handles string responses correctly
   - Ensure MCP protocol compatibility

### Step 5: Add Tests

1. **Unit tests**:
   - Test `_build_response()` returns valid JSON
   - Test `_create_error_result()` returns valid JSON
   - Test JSON can be parsed with `json.loads()`

2. **Integration tests**:
   - Test tool call via MCP protocol (if possible)
   - Test tool call directly via Python (should still work)
   - Verify response format matches expected structure

3. **Regression tests**:
   - Ensure fix doesn't break existing functionality
   - Test all check types (fix_errors, format, type_check, quality, tests)
   - Verify error handling still works

### Step 6: Update Documentation

1. **Update tool docstring**:
   - Clarify return type (dict vs str)
   - Update examples if return type changes
   - Document any breaking changes

2. **Update commit workflow**:
   - Update commit.md if tool interface changes
   - Ensure examples use correct return type
   - Document any migration needed

## Success Criteria

- ✅ `execute_pre_commit_checks` MCP tool works when called via MCP protocol
- ✅ No JSON parsing errors when calling tool via MCP
- ✅ Tool still works when called directly via Python
- ✅ All pre-commit checks (fix_errors, format, type_check, quality, tests) work via MCP
- ✅ Commit procedure can use MCP tool directly (no terminal fallback needed)
- ✅ All tests pass
- ✅ No regressions in existing functionality

## Risks & Mitigation

### Risk 1: Breaking Change for Direct Python Calls

**Risk**: Changing return type from `str` to `dict` might break code that calls the tool directly.

**Mitigation**:

- Check for all direct calls to `execute_pre_commit_checks()`
- Update callers to handle dict return type
- Add compatibility layer if needed

### Risk 2: FastMCP Version Compatibility

**Risk**: FastMCP version might not support dict return types or might have different behavior.

**Mitigation**:

- Check FastMCP version and documentation
- Test with different return types
- Implement version-specific handling if needed

### Risk 3: Other Tools Affected

**Risk**: Fix might reveal similar issues in other tools that return JSON strings.

**Mitigation**:

- Audit all MCP tools for string return types
- Test all tools via MCP protocol
- Fix similar issues proactively

## Dependencies

- FastMCP framework behavior understanding
- MCP protocol specification
- Existing test infrastructure

## Timeline

- **Investigation**: 1-2 hours
- **Implementation**: 1-2 hours
- **Testing**: 1 hour
- **Total**: 3-5 hours

## Notes

- This is a BLOCKER that prevents proper commit procedure execution
- Priority is ASAP to unblock commit workflow
- Should be completed before next commit attempt
- May require FastMCP documentation or source code review
