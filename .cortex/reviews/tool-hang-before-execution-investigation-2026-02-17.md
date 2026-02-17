# Investigation: Tool Hang Before Execution (No Tool Calls)

**Date:** 2026-02-17  
**Transcript:** `0d491698-c0b8-4c38-aea0-4a821be165fa.txt`  
**Command:** `/cortex/fix_quality`

---

## Summary

The agent never started processing the command - there are **no tool calls or assistant responses** in the transcript. The transcript ends immediately after the user query, suggesting the agent hung before it could even begin executing.

---

## What Happened

From the transcript:

1. **User query**: `/cortex/fix_quality` command issued
2. **No assistant response**: Transcript ends with no tool calls, no thinking, no response
3. **Complete hang**: Agent appears to be blocked before any execution begins

**Transcript length**: Only 82 lines (just the command prompt, no execution)

---

## Root Cause Analysis

### Possible Causes

1. **Agent Initialization Blocking**:
   - The agent may be waiting for MCP connection initialization
   - Prompt loading/processing may be blocked
   - Agent context setup may be hanging

2. **MCP Server Startup Blocking**:
   - Server may be waiting for client connection
   - Tool registration may be blocked
   - Manager initialization may be blocking server startup

3. **Concurrent Tool Execution Blocking**:
   - If another long-running tool is executing (e.g., `execute_pre_commit_checks`, `fix_quality_issues`), the serial semaphore may be held
   - New tool calls wait up to `LONG_RUNNING_SEMAPHORE_WAIT_SECONDS = 330.0` seconds (5.5 minutes)
   - But this shouldn't prevent the agent from starting to process

4. **Client-Side Blocking**:
   - Cursor may be waiting for MCP server response
   - Client-side timeout may be preventing agent from starting
   - Connection issues may prevent agent initialization

### Most Likely Cause

**Client-side blocking or MCP connection issue** - The agent never received the command or is blocked waiting for MCP server initialization. This is different from tool execution hangs where tools are called but hang during execution.

---

## Comparison with Previous Hang

| Aspect | Previous Hang (f666c731) | Current Hang (0d491698) |
|--------|-------------------------|------------------------|
| **Tool calls** | ✅ Tools were called | ❌ No tool calls |
| **Tool results** | Empty results returned | No results (no calls) |
| **Agent response** | Partial response | No response |
| **Stage** | During tool execution | Before tool execution |
| **Likely cause** | Tool blocking/timeout | Client/server initialization |

---

## Investigation Steps

### 1. Check MCP Server Status

Verify the MCP server is running and responsive:

- Check server logs for errors
- Verify connection is established
- Check if other tools are executing concurrently

### 2. Check for Blocking Operations

- **Serial semaphore**: Check if `fix_quality_issues` or other long-running tools are executing
- **Manager initialization**: Check if manager initialization is blocked
- **File locks**: Check for stale file locks that might block initialization

### 3. Check Client-Side Behavior

- **Cursor logs**: Check Cursor logs for MCP connection issues
- **Timeout settings**: Verify client-side timeouts aren't too aggressive
- **Connection state**: Verify MCP connection is healthy

### 4. Check for Deadlocks

- **Init lock**: Check if `_usage_context_init_lock` is held indefinitely
- **Semaphore wait**: Check if tools are waiting for semaphore release
- **File locks**: Check for circular file lock dependencies

---

## Recommendations

### Immediate Actions

1. **Check MCP Server Health**:

   ```python
   # Use check_mcp_connection_health tool if available
   # Or check server logs directly
   ```

2. **Verify No Concurrent Long-Running Tools**:
   - Check if `fix_quality_issues`, `execute_pre_commit_checks`, or `fix_markdown_lint` are running
   - If yes, wait for them to complete or timeout

3. **Check Client Connection**:
   - Restart Cursor if connection appears stale
   - Verify MCP server is responding to other requests

### Long-Term Improvements

1. **Add Timeout to Agent Initialization**:
   - Set maximum time for agent to start processing
   - Log warnings if initialization takes > 10 seconds

2. **Better Error Reporting**:
   - Surface clearer errors when agent fails to start
   - Distinguish between "tool hang" and "agent initialization hang"

3. **Connection Health Monitoring**:
   - Add periodic health checks
   - Alert when connection appears stale

---

## Related Issues

- **Tool Hang Investigation** (f666c731): Tools called but returned empty results
- **Connection Closed Investigation** (d3c1b4ce): Tools executed but connection closed
- **MCP Failure Handler Fix**: Fixed `.cortex` directory detection issue

---

## Status

**Status**: 🔍 Investigation needed  
**Priority**: High - Complete hang prevents any tool execution  
**Next Steps**:

1. Check MCP server logs
2. Verify no concurrent long-running tools
3. Check client connection health
4. Investigate agent initialization blocking
