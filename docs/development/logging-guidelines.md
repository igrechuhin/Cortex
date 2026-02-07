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

Tools accept an optional `ctx: MCPContext | None` parameter (injected by the server when available). Use `log_client()` so messages go to the client when `ctx` is present and to the server logger otherwise:

```python
from cortex.core.context_logging import MCPContext, log_client

@mcp.tool()
@mcp_tool_wrapper(timeout=...)
async def my_tool(param: str, ctx: MCPContext | None = None) -> str:
    await log_client(ctx, "info", "Starting my_tool")
    # ... tool logic ...
    await log_client(ctx, "info", "my_tool completed")
    return result
```

For long-running work, use `report_progress_safe()` from `cortex.core.context_logging` so progress is sent to the client when context is available.

### Log Levels

- **debug**: Detailed diagnostics (e.g. intermediate steps). Use sparingly for client.
- **info**: Normal operation progress (start, completion, milestones).
- **warning**: Non-critical issues (e.g. fallback used, deprecated path).
- **error**: Errors that allow continuation; client should see the message.

### Progress Reporting

For long-running operations, use `report_progress_safe()` so progress is only sent when context is available (no-op in tests or when client disconnected):

```python
from cortex.core.context_logging import report_progress_safe

await report_progress_safe(ctx, progress=50, total=100)
```

### Fatal Errors

Use `ToolError` (from MCP/FastMCP) for errors that should stop execution and be shown to the client. Do not log sensitive details in client-visible messages.

### Context Availability

Context is only available during MCP request handling. Tools and helpers accept `ctx: MCPContext | None = None` and use `log_client(ctx, level, message)` and `report_progress_safe(ctx, progress, total)` so logging is a no-op when `ctx` is None (e.g. in tests or after client disconnect).

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
