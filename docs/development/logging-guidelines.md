# Logging Guidelines

This document describes how to use logging in Cortex so that client-visible messages use MCP Context logging and server-side diagnostics use standard Python logging.

## Overview

- **Context logging** (`ctx.debug`, `ctx.info`, `ctx.warning`, `ctx.error`): Messages sent to the MCP client. Use for operation progress, user-facing warnings, and errors.
- **Standard Python logging** (`logger.debug`, `logger.info`, etc.): Messages to stderr for server-side debugging. Use for internal state and detailed diagnostics.

## When to Use Each

| Audience        | Use Context logging      | Use standard logging      |
|----------------|--------------------------|----------------------------|
| Client/user    | Operation start/end      | —                          |
| Client/user    | Progress (long operations)| —                          |
| Client/user    | Warnings, non-fatal errors| —                          |
| Server/debug   | —                        | Detailed diagnostics       |
| Server/debug   | —                        | Internal state, traces     |

## Context Logging (MCP)

### Accessing Context in Tools

Add a parameter with the `Context` type annotation; the MCP server injects it:

```python
from mcp.server.fastmcp import Context

@mcp.tool()
@mcp_tool_wrapper(timeout=...)
async def my_tool(param: str, ctx: Context) -> str:
    await ctx.info("Starting my_tool")
    # ... tool logic ...
    await ctx.info("my_tool completed")
    return result
```

### Log Levels

- **debug**: Detailed diagnostics (e.g. intermediate steps). Use sparingly for client.
- **info**: Normal operation progress (start, completion, milestones).
- **warning**: Non-critical issues (e.g. fallback used, deprecated path).
- **error**: Errors that allow continuation; client should see the message.

### Progress Reporting

For long-running operations, use progress instead of many log lines:

```python
await ctx.report_progress(progress=50, total=100)
```

### Fatal Errors

Use `ToolError` (from MCP/FastMCP) for errors that should stop execution and be shown to the client. Do not log sensitive details in client-visible messages.

### Context Availability

Context is only available during MCP request handling. In helper functions, accept an optional `ctx: Context | None` and only call `ctx.*` when `ctx` is not None.

## Standard Logging (Server-Side)

- Use `logging.getLogger(__name__)` at module level.
- Use `logger.debug()` for detailed traces, `logger.info()` for server lifecycle, `logger.warning()` / `logger.error()` for server-side issues.
- Do not rely on standard logs for client-visible messages; use Context logging for that.

## Message Format

- Keep messages short and actionable.
- Do not include secrets or PII in client-visible messages.
- Prefer structured data in `extra` when the Context API supports it (e.g. `tool_name`, `request_id`).

## Required Metadata (When Supported)

Where the Context API allows extra fields, include when useful:

- `tool_name`: Name of the tool (e.g. `manage_file`).
- `request_id`: From `ctx.request_id` when correlating logs.

## Decision Tree

1. Is the message for the client (progress, outcome, warning, error)?  
   → Use Context logging (`ctx.info`, `ctx.warning`, `ctx.error`, `ctx.report_progress`).
2. Is the message for server debugging or internal state?  
   → Use standard logging (`logger.debug`, `logger.info`, etc.).
3. Both?  
   → Use Context for the client message and optionally logger for the detailed server-side trace.
