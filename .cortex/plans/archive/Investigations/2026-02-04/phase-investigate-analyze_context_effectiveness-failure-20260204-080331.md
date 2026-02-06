# Phase: Investigate analyze_context_effectiveness MCP Tool Failure

**Status**: COMPLETE
**Priority**: ASAP (Blocker)
**Created**: 2026-02-04
**Completed**: 2026-02-04

## Goal

Investigate and fix MCP tool failure that occurred during commit procedure execution.

## Context

**Problem**: The `analyze_context_effectiveness` MCP tool failed during step: **MCP tool execution**

**Error Details**:

- **Error Type**: `TypeError`
- **Error Message**: `analyze_context_effectiveness() got an unexpected keyword argument 'project_root'`

**Impact**: Commit procedure blocked at step: MCP tool execution. This is a blocker.

## Root Cause

The error occurred because legacy code was attempting to pass `project_root` as a parameter to MCP tools. However, all MCP tools resolve `project_root` internally using `resolve_project_root_async(None, ctx)` and do not accept it as a parameter. The legacy code path was stripping `project_root` from kwargs before passing to tools, but this was inconsistent with the design where tools resolve root internally.

## Solution

Removed all legacy support for `project_root` being passed to tools:

1. **Removed legacy stripping**: Removed code that stripped `project_root` from kwargs in `ensure_usage_context` wrapper (line 83 in `mcp_stability.py`)
2. **Removed defensive exclusion**: Removed `project_root` from exclusion list in `_stability_params` (line 471)
3. **Updated tests**: Modified tests to verify that `project_root` is now passed through (not stripped), and tools that don't accept it will raise `TypeError` to enforce migration

## Implementation Steps

1. ✅ Analyzed error type and message, checked tool implementation
2. ✅ Removed legacy `project_root` handling from `mcp_stability.py`
3. ✅ Updated tests to verify new behavior (tests pass)

## Success Criteria

- ✅ Root cause identified and fixed
- ✅ Tool works correctly via MCP protocol (tools resolve root internally)
- ✅ Legacy callers will receive TypeError, forcing migration
- ✅ Tests updated and passing

## Notes

- The `analyze_context_effectiveness` tool already resolves `project_root` internally (line 73 in `context_analysis_handlers.py`), so it's correct.
- Tools that don't accept `project_root` will now raise `TypeError` if it's passed, which enforces migration away from legacy patterns.
- All tools resolve `project_root` internally using `resolve_project_root_async(None, ctx)` via the `ensure_usage_context` decorator.
