# Phase: Investigate fix_quality_issues MCP Tool Failure

**Status**: COMPLETE (2026-02-04)
**Priority**: ASAP (Blocker) - RESOLVED
**Created**: 2026-02-04
**Target Completion**: 2026-02-04

## Goal

Investigate and fix MCP tool failure that occurred during commit procedure execution.

## Context

**Problem**: The `fix_quality_issues` MCP tool failed during step: **MCP tool execution**

**Error Details**:

- **Error Type**: `TypeError`
- **Error Message**: `fix_quality_issues() got an unexpected keyword argument 'project_root'`

**Impact**: Commit procedure blocked at step: MCP tool execution. This is a blocker.

## Requirements

1. **Investigate**: Analyze error, check tool implementation, verify MCP
   protocol compliance
2. **Fix**: Resolve root cause, ensure tool works via MCP protocol
3. **Verify**: Test tool, verify commit procedure proceeds, ensure no regressions

## Implementation Steps

1. Analyze error type and message, check tool implementation
2. Fix root cause, add error handling/validation
3. Add tests for failure scenarios, verify fix works

## Resolution (2026-02-04, revised)

- **Root cause**: The MCP stability layer (and/or clients) could pass a `project_root`
  keyword in tool arguments (e.g. for usage-context setup). Tool handlers are expected to
  **resolve root internally** and do not accept `project_root`. That mismatch caused
  `TypeError: fix_quality_issues() got an unexpected keyword argument 'project_root'`
  when the tool was invoked with that argument.
- **Fix** (strip at stability layer; no tool API change):
  - In `src/cortex/core/mcp_stability.py`, `_stability_params` now excludes `project_root`
    from `func_kwargs`, so it is never passed through to the tool. `project_root` remains
    available to `ensure_usage_context` for manager/context setup only.
  - `fix_quality_issues` (and all other tools) continue to resolve root internally via
    `resolve_project_root_async(None, ctx)`; they do not accept `project_root`.
  - Unit tests in `tests/unit/test_mcp_stability_timeouts.py` (class
    `TestProjectRootStrippedFromToolKwargs`) verify that `with_mcp_stability` strips
    `project_root` from kwargs before calling the tool and still passes through other
    tool-specific kwargs.
- **Verification**:
  - `tests/unit/test_mcp_stability_timeouts.py` and `tests/unit/test_pre_commit_tools.py`
    pass; lint/type checks clean.

## Success Criteria

- Root cause identified and fixed
- Tool works correctly via MCP protocol
- Commit procedure can proceed, no regressions

## Notes

Auto-generated on MCP tool failure. Tool: fix_quality_issues, Error:
TypeError: fix_quality_issues() got an unexpected keyword argument 'project_root'
