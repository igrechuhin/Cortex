---
title: "FastMCP v3 — Phase 3: Middleware for Disconnect Handling and Request Logging"
component: "server"
work_type: migration
status: PENDING
priority: Medium
created: 2026-04-13
depends_on:
  - fastmcp-v3-phase2-official-lifecycle-apis
---

## FastMCP v3 — Phase 3: Middleware for Disconnect Handling and Request Logging

## Goal

Replace the `_patch_mcp_server_handle_request` MethodType monkey-patch (which
silences `ClosedResourceError` on client disconnect) with a proper FastMCP v3
middleware. Add a `LoggingMiddleware` for agent-oriented request/response
tracing while the middleware pipeline is open.

## Context

FastMCP v3 introduces a production-ready middleware system:

```text
Request → Middleware A → Middleware B → operation → Middleware B → Middleware A → Response
```

Two middleware types:

- **List middleware**: receives the full sequence for `list_tools`,
  `list_resources`, `list_prompts`
- **Get middleware** (chain pattern): uses `call_next` for `get_tool`,
  `get_resource`, `get_prompt`

Currently Cortex absorbs `ClosedResourceError` (and a family of connection
errors) via a MethodType patch on the private `_handle_request` method. This
is the right job for middleware.

Existing structured logging (`src/cortex/tools/logging/`) emits JSON lines
to stderr. Adding `LoggingMiddleware` from fastmcp v3 gives human-readable
MCP-level traces for request/response pairs, complementing the JSON log.

## Implementation Steps

### Step 1 — Read disconnect-handling code in main.py

Read `src/cortex/main.py` lines 234–300:

- `_patch_mcp_server_handle_request` (the MethodType patch)
- `_run_mcp_with_transport_handlers` (the top-level error mapping)
- `handle_broken_resource_in_group` (BaseExceptionGroup handler)

Map exactly which exceptions are caught where:

- `ClosedResourceError` — in `_patched._handle_request` (per-request)
- `BrokenResourceError`, `ClosedResourceError`, `BrokenPipeError`, `ConnectionError`
  — in `_run_mcp_with_transport_handlers` (process-level)

Determine which of these are appropriate for middleware vs top-level handling.

### Verification checklist 1

- [ ] Full list of suppressed exception types documented per catch site
- [ ] Per-request vs process-level distinction is clear

### Step 2 — Investigate FastMCP v3 middleware API

Check fastmcp v3 docs and source (`fastmcp/middleware.py` or similar) for:

1. Exact middleware base class / protocol
2. Whether middleware can catch exceptions from the underlying operation
3. The `LoggingMiddleware` class (built-in or example)
4. How to register middleware: `mcp.add_middleware(...)` or constructor param

### Verification checklist 2

- [ ] Middleware base class/protocol confirmed
- [ ] Exception-catching middleware pattern confirmed (try/except around `call_next`)
- [ ] `LoggingMiddleware` class confirmed

### Step 3 — Implement `DisconnectMiddleware`

Create `src/cortex/server_middleware.py`:

```python
from fastmcp.middleware import Middleware  # verify exact import
from anyio import ClosedResourceError

class DisconnectMiddleware(Middleware):
    """Absorb ClosedResourceError when a client disconnects mid-request."""

    async def on_call_tool(self, context, call_next):
        try:
            return await call_next(context)
        except ClosedResourceError:
            logger.debug(
                "Response dropped: client disconnected (request_id=%s)",
                getattr(context, "request_id", "?"),
            )
            return None  # or appropriate no-op return type

    # Repeat pattern for on_read_resource, on_get_prompt if middleware
    # covers those operations too
```

Adjust to the actual v3 middleware API once confirmed in Step 2.

Register in `server.py`:

```python
from cortex.server_middleware import DisconnectMiddleware
mcp.add_middleware(DisconnectMiddleware())
```

After middleware is registered and tested, remove `_patch_mcp_server_handle_request`
from `main.py`.

### Verification checklist 3

- [ ] `DisconnectMiddleware` registered via official v3 API
- [ ] `ClosedResourceError` absorbed without crashing server
- [ ] `_patch_mcp_server_handle_request` removed from `main.py`
- [ ] No `MethodType` / `getattr(lowlevel, "_handle_request")` usage remains

### Step 4 — Add `LoggingMiddleware` for MCP-level tracing

Register FastMCP v3's built-in `LoggingMiddleware` (if available) in
`server.py` **only when** `CORTEX_DEBUG=1` or `CORTEX_MCP_LOG_LEVEL=debug`
is set, to avoid verbose output in production stdio sessions.

```python
import os
from fastmcp.middleware import LoggingMiddleware  # verify exact import

if os.environ.get("CORTEX_DEBUG") == "1":
    mcp.add_middleware(LoggingMiddleware())
```

If fastmcp v3 does not ship a built-in `LoggingMiddleware`, implement a minimal
one that logs tool name + call duration to the existing
`cortex.tools.logging.emit` channel.

### Verification checklist 4

- [ ] MCP request/response pairs logged at DEBUG level
- [ ] No logging output in normal stdio mode
- [ ] Existing JSON-line agent logging (`cortex.tools.logging`) unaffected

### Step 5 — Add `ResponseLimitMiddleware` for context-window safety

FastMCP v3 ships a response-limiting middleware. Register it with sensible
defaults to prevent runaway tool responses from overflowing context windows:

```python
from fastmcp.middleware import ResponseLimitMiddleware  # verify exact import
mcp.add_middleware(ResponseLimitMiddleware(max_tokens=50_000))
```

The limit should be configurable via `.cortex/config/optimization.json`
(already used for tool search config). Add a `max_response_tokens` key to
the schema.

If the built-in middleware is too coarse, implement a custom one that truncates
`TextContent` responses that exceed the budget while preserving the tail
(`# AI: tail preserved for debugging`).

### Verification checklist 5

- [ ] Oversized tool responses are truncated with a clear notice
- [ ] Normal responses are not affected
- [ ] Limit is configurable from `optimization.json`
- [ ] Unit tests for truncation behavior

### Step 6 — Quality gate

`run_quality_gate()`. All tests pass.

### Verification checklist 6

- [ ] `src/cortex/main.py` contains no `_patch_mcp_server_handle_request`
- [ ] All disconnect/connect error tests pass
- [ ] Coverage ≥90%

## Dependencies

- Phase 2 complete (official lifecycle APIs in place).

## Success Criteria

1. `_patch_mcp_server_handle_request` deleted from `main.py`.
2. `DisconnectMiddleware` handles `ClosedResourceError` via official middleware.
3. `LoggingMiddleware` active at debug level.
4. `ResponseLimitMiddleware` prevents context-window overflow.
5. All tests pass, quality gate green.

## Testing Strategy

- **Unit tests** (Steps 3–5): mock middleware context; assert exceptions are
  caught; assert large responses are truncated; assert normal responses pass
  through.
- **Integration**: simulate client disconnect mid-call; verify server does not
  crash.
- **New tests file**: `tests/unit/test_server_middleware.py`.

Coverage target: 95% for `server_middleware.py`.
