# Phase 58: Fix execute_pre_commit_checks Timeout Protection

**Status**: COMPLETE  
**Priority**: ASAP (Blocker)  
**Created**: 2026-01-28  
**Completed**: 2026-01-28  
**Related**: Phase 34, Phase 57

## Goal

Add timeout protection to `execute_pre_commit_checks` MCP tool to prevent server hangs and crashes when checks hang or take too long.

## Problem Statement

The `execute_pre_commit_checks` MCP tool lacks timeout protection via `@mcp_tool_wrapper(timeout=...)` decorator. When the tool is called and any of its checks (fix_errors, format, type_check, quality, tests) hang or take too long, the entire MCP server becomes unresponsive.

**Evidence from logs**:

1. **Long-Running Operations**: Checks can perform long-running operations:
   - `fix_errors`: Can run ruff/black which may hang on large codebases
   - `quality`: Can scan many files for size/function length violations
   - `tests`: Can run for a very long time (has its own timeout parameter)

### Comparison with Other Tools

1. **Timeout Enforcement**: Test that timeout is enforced when operations hang
2. **Error Handling**: Verify timeout errors are properly returned as JSON responses

- ✅ Timeout value is appropriate for the tool's complexity

## Implementation

### Changes Made

1. **Added imports** in `src/cortex/tools/pre_commit_tools.py`:
   - `from cortex.core.constants import MCP_TOOL_TIMEOUT_VERY_COMPLEX`
   - `from cortex.core.mcp_stability import mcp_tool_wrapper`

2. **Added timeout decorator** to `execute_pre_commit_checks` with **correct decorator order**:

- ✅ Decorator order matches other tools (`@mcp.tool()` then `@mcp_tool_wrapper()`)
- ✅ Imports are correct and follow project conventions
- ✅ Timeout value is appropriate for the tool's complexity

## Verification

1. ✅ **Timeout decorator verified**: Test `test_has_timeout_protection` confirms timeout wrapper is correctly applied
2. ✅ **Timeout value verified**: `MCP_TOOL_TIMEOUT_VERY_COMPLEX = 600.0` seconds (10 minutes) is appropriate for complex operations
3. ✅ **Related fix**: Fixed `FileMetadataForScoring` validation error in `load_context` that was blocking context loading (sections normalization)

## Next Steps
