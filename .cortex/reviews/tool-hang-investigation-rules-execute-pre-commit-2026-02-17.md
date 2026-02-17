# Investigation: Tool Hang - rules and execute_pre_commit_checks

**Date:** 2026-02-17  
**Transcript:** `f666c731-afce-41e4-b98b-f7b1a6a196df.txt`

---

## Summary

Both `rules` and `execute_pre_commit_checks` tools appear to hang when called concurrently. The transcript shows both tools were invoked but returned empty results, suggesting they may be blocking or timing out.

---

## What Happened

From the transcript:

1. Agent called `rules(operation="get_relevant", task_description="Type, lint, and formatting fixes")`
2. Agent called `execute_pre_commit_checks(checks=["type_check","quality","format"], ...)`
3. Both tools show `[Tool result]` entries but with **no actual content**
4. This suggests the tools either:
   - Are still running (taking longer than expected)
   - Completed but results were lost/dropped
   - Are blocked waiting for a resource

---

## Root Cause Analysis

### Tool Characteristics

1. **`execute_pre_commit_checks`**:
   - Uses serial semaphore (only one instance at a time)
   - Timeout: `MCP_TOOL_TIMEOUT_VERY_COMPLEX = 960.0` seconds (16 minutes)
   - In `long_running_tools_serialized` set
   - Can take 1-3+ minutes for fix_errors/format with no progress updates

2. **`rules`**:
   - NOT in serialized tools list (should run concurrently)
   - Timeout: `MCP_TOOL_TIMEOUT_MEDIUM = 120.0` seconds (2 minutes)
   - Calls `get_managers()` which may block on initialization
   - Calls `rules_manager.initialize()` which may do file I/O

### Potential Issues

1. **Manager Initialization Blocking**:
   - Both tools call `get_managers()` which initializes managers
   - If manager initialization involves file locks or slow I/O, concurrent calls might block
   - `rules` calls `rules_manager.initialize()` which may index rules files

2. **File Lock Contention**:
   - If both tools access the same files (e.g., `.cortex/config/optimization.json`), file locks could cause blocking
   - Rules indexing may lock files that other operations need

3. **Semaphore Wait Timeout**:
   - `execute_pre_commit_checks` waits up to `LONG_RUNNING_SEMAPHORE_WAIT_SECONDS = 330.0` seconds (5.5 minutes) for the semaphore
   - If another long-running tool is already running, this could appear as a hang

4. **Missing Progress Updates**:
   - `rules` doesn't report progress, so if it's slow, it appears frozen
   - `execute_pre_commit_checks` only reports progress for tests, not for fix_errors/format

---

## Evidence

### Code References

- `src/cortex/core/mcp_stability_config.py:102-103`: `rules` is NOT in `long_running_tools_serialized`
- `src/cortex/core/mcp_stability_config.py:109`: Semaphore wait timeout is 330 seconds
- `src/cortex/tools/rules_operations.py:500-508`: `rules` calls `get_managers()` and `rules_manager.initialize()`
- `src/cortex/tools/pre_commit_tools.py:294`: `execute_pre_commit_checks` uses serial semaphore

### Related Issues

- Phase 58: Fixed timeout protection for `execute_pre_commit_checks`
- Review: `commit-pipeline-hang-and-timeout-investigation-2026-02-08.md` - Similar hang issues documented

---

## Recommendations

### Immediate Fixes

1. **Add Progress Reporting to `rules`**:
   - When `rules` operation takes > 5 seconds, report progress
   - Helps identify if tool is actually running vs hung

2. **Check for File Lock Contention**:
   - Verify that `rules` indexing doesn't lock files needed by other tools
   - Consider using read-only locks for indexing operations

3. **Add Timeout Logging**:
   - Log when tools approach their timeout limits
   - Helps identify slow operations before they timeout

### Long-term Improvements

1. **Manager Initialization Optimization**:
   - Ensure `get_managers()` is truly concurrent-safe
   - Consider caching managers more aggressively to avoid repeated initialization

2. **Tool Dependency Analysis**:
   - Document which tools can safely run concurrently
   - Consider adding tool dependency graph to prevent conflicts

3. **Better Error Reporting**:
   - When tools timeout or hang, return structured error messages
   - Include diagnostic information (what was blocked, why)

---

## Testing

To reproduce and verify fixes:

1. Call `rules` and `execute_pre_commit_checks` concurrently
2. Monitor tool execution time and progress updates
3. Check for file locks or semaphore contention
4. Verify both tools complete successfully

---

## Status

**Status**: Investigation complete, recommendations provided  
**Next Steps**: Implement progress reporting for `rules` tool, verify manager initialization concurrency
