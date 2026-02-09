# Investigation: FastMCP Blocking Before Tool Handler Invocation

**Status**: IN PROGRESS  
**Created**: 2026-02-09  
**Priority**: **CRITICAL** - Blocks all MCP tool usage  
**Blocker**: Yes - ASAP priority

## Problem Statement

When Cortex MCP server is enabled, Cursor experiences `resource_exhausted` errors when trying to use prompts or make tool calls. The error occurs ~25-30 seconds after prompt retrieval, with no tool call requests appearing in bridge logs and no tool handler invocations.

## Symptoms

1. **Prompt retrieval succeeds**: Logs show prompt retrieval completes successfully
2. **No tool call requests**: After prompt retrieval, no tool call requests appear in bridge logs
3. **No handler invocations**: No "FastMCP CALLED tool handler" messages appear (despite comprehensive logging)
4. **Timeout**: Cursor times out with `resource_exhausted` error ~25-30 seconds later

## Evidence

### Log Analysis

From logs (2026-02-09 18:59:33):

- Line 407: Prompt 'commit' retrieved successfully
- Lines 395-405: Bridge forwards prompt request and receives response
- **Missing**: No tool call requests after prompt retrieval
- **Missing**: No "FastMCP CALLED tool handler" messages
- Line 408: DeleteClient action ~27 seconds later (timeout/cleanup)

### Logging Added

1. **Direct stderr write in tool wrapper** (`src/cortex/core/mcp_stability.py:851`):
   - Logs immediately when FastMCP calls our handler
   - Uses `sys.stderr.write()` to bypass any logging blocking
   - **Result**: Never appears in logs

2. **Enhanced bridge logging** (`src/cortex/bridge.py`):
   - Distinguishes tool call requests vs responses
   - Logs all message forwarding
   - **Result**: Shows prompt requests/responses but no tool call requests after prompt retrieval

3. **Logging around mcp.run()** (`src/cortex/main.py:246-255`):
   - Logs when `mcp.run()` is called and when it returns
   - **Result**: Shows server starts but doesn't show blocking (mcp.run() is blocking call)

## Root Cause Hypothesis

FastMCP is blocking during request parsing/routing **before** it calls our tool handlers. Possible causes:

1. **Synchronous I/O during request parsing**: FastMCP might be doing blocking file I/O or network calls when parsing tool call requests
2. **Tool registration lookup blocking**: When FastMCP tries to find the right tool handler, it might be doing something synchronous that blocks
3. **HTTP server blocking**: The streamable-http transport might have a blocking operation during request handling
4. **Request validation blocking**: FastMCP might be doing synchronous validation that blocks

## Investigation Steps

1. **Verify FastMCP version and known issues**:
   - ✅ Current: Using `mcp` SDK 1.26.0 with FastMCP from `mcp.server.fastmcp`
   - ⚠️ **ACTION**: Consider migrating to standalone `fastmcp` package v2.14.5 (latest stable)
   - Check FastMCP version in `requirements.txt` / `pyproject.toml`
   - Search for known issues with streamable-http transport
   - Check if there are any blocking operations in FastMCP's request handling
   - **Note**: Phase 41 plan mentions migration to FastMCP 2.14.3 was complete, but code still uses `from mcp.server.fastmcp import FastMCP` - migration may not have been fully completed

2. **Test with different transport**:
   - Try using stdio transport directly (bypass bridge)
   - Try using SSE transport
   - Compare behavior across transports

3. **Minimal reproduction**:
   - Create a minimal FastMCP server with one tool
   - Test if the issue reproduces with minimal setup
   - Isolate whether it's FastMCP or our code

4. **Check FastMCP source code**:
   - Review FastMCP's request handling code
   - Look for synchronous operations in request parsing/routing
   - Check if there are any blocking calls during tool lookup

5. **Monitor FastMCP's internal state**:
   - Add logging at HTTP server level (if possible)
   - Check if requests are reaching FastMCP's HTTP handler
   - Verify if FastMCP is processing requests but blocking before handler invocation

## Workarounds

None currently identified. The issue blocks all tool usage.

## FastMCP GitHub Issues Check (2026-02-09)

Searched [jlowin/fastmcp issues](https://github.com/jlowin/fastmcp/issues):

- **No exact match**: No open/closed issue describes "tool handler not called after prompt" or "resource_exhausted" with streamable-http and Cursor.
- **Related – FastMCP #3113** ([open](https://github.com/jlowin/fastmcp/issues/3113)): *"FastMCP.from_openapi() tool call fails on some models like claude when tool call with POST parameters in prompt"* – Copilot fails with "Error parsing JSON stream data" / Internal Server Error when using streamable-http (`mcp.run(transport="http", ...)`). Different scenario (OpenAPI-generated tools) but same stack: FastMCP 2.14.5, streamable HTTP, IDE client.
- **Related – MCP Go SDK #633** ([open](https://github.com/modelcontextprotocol/go-sdk/issues/633)): *"Streamable HTTP clients can get stuck connecting"* – Client can hang waiting for the first notification from the server, especially if the server doesn’t flush the response buffer after writing headers. Suggests streamable HTTP connection lifecycle can cause client-side timeouts.

**Conclusion**: Not a known FastMCP issue with the exact Cortex/Cursor symptoms. Worth opening a new issue with a minimal repro (streamable-http + Cursor, prompt then tool call never reaches handler / resource_exhausted) if the FunctionTool wrapper fix does not resolve it.

## manage_file Hangs (2026-02-09)

**Symptom**: Calls to `manage_file` hang (never return).

**Likely causes addressed**:

1. **Blocking event loop in project root fallback**  
   When the cached project root is missing, `resolve_project_root_async()` called `_fallback_root()` synchronously. That runs `get_project_root(None)` (filesystem walks) on the event loop and can block all tools.  
   **Fix**: Run `_fallback_root()` in `asyncio.to_thread()` so it never blocks the event loop (`project_root_resolver.py`).

2. **Unbounded wait on usage context init lock**  
   If the first tool call is slow or stuck in `get_managers()`, other tool calls wait on the init lock with no timeout and can hang indefinitely.  
   **Fix**: Acquire the usage context init lock with a 25s timeout (`MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS`). On timeout, log and raise `RuntimeError` so the call fails instead of hanging (`mcp_stability.py`, `constants.py`).

**Other potential hang points** (unchanged, but bounded):

- **get_managers()**: Already wrapped in 15s timeout in `_resolve_root_and_managers`.
- **File lock (writes)**: `FileSystemManager` uses 5s lock timeout; `manage_file` write can wait up to 5s for a lock.

## Next Steps

1. ~~Check FastMCP version and known issues~~ Done; see "FastMCP GitHub Issues Check" above.
2. Test with minimal FastMCP server to isolate issue.
3. Review FastMCP source code for blocking operations.
4. If still broken after FunctionTool fix: open a FastMCP issue with minimal repro and link this plan.

## Related

- Previous investigation: `.cortex/plans/archive/Investigations/2026-02-07/investigate-mcp-connection-closed-2026-02-07.md`
- MCP transport analysis: `docs/mcp-transport-http-sse-analysis.md`
