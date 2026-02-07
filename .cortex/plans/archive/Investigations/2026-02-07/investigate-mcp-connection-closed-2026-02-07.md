# Investigation: MCP connection closed during fix_markdown_lint (2026-02-07)

## Summary

**Observed**: Cursor MCP client disconnected while the `fix_markdown_lint` tool was running. The client saw `MCP error -32000: Connection closed`; the server logged "MCP stdio connection broken during TaskGroup cleanup (client disconnected)".

**Root cause**: The **client (Cursor) closed the MCP stdio connection** while the tool was still in progress—likely due to a client-side tool-call timeout or UI/process behavior, not a server bug.

---

## Log evidence (user-cortex MCP log)

| Time       | Event |
|-----------|--------|
| 13:00:54  | `fix_markdown_lint` called (tool_7939cd4f...) |
| 13:00:55  | Progress 0/10 |
| 13:01:00  | Progress 1/10 |
| …         | Progress 2–8/10 (~every 5–6 s) |
| 13:01:44  | Progress 9/10 |
| 13:01:49  | Cursor sends ListOfferings (client still active) |
| 13:01:50  | **Server**: "MCP stdio connection broken during TaskGroup cleanup (client disconnected); … ExceptionGroup" |
| 13:01:50  | **Client**: "Error calling tool 'fix_markdown_lint': MCP error -32000: Connection closed" |
| 13:01:50  | "Client closed for command" |
| After     | ListOfferings returns 0 tools / 0 prompts / 0 resources (client lost connection to server) |
| 13:40:35  | DeleteClient → CreateClient → new server process; 52 tools / 8 prompts / 16 resources again |

So the tool ran **~56 seconds** (13:00:54 → 13:01:50) and the client was still receiving progress (0→9/10) about every 5–6 s. The disconnect happened shortly after the last progress (9/10), during or right after completion.

---

## Root cause

1. **Server behavior**: The server was still sending progress and had a 15 s heartbeat (`MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS`) and per-file progress. So the connection was not idle for long periods.
2. **Client behavior**: The client closed the connection. The log text "client disconnected" and "Client closed for command" indicates the close was initiated or detected on the client side.
3. **Likely explanations**:
   - **Client-side tool-call timeout**: Cursor may enforce a maximum duration for a single tool call (e.g. ~60 s), after which it closes the connection even if progress is being sent.
   - **User/IDE action**: User closed the chat, switched context, or the IDE reinitialized the MCP client.
   - **Process/stdio lifecycle**: The client process that owned the stdio transport was torn down (e.g. reconnection flow), which would show as "client disconnected" on the server.

So this instance of "Connection closed" is **client-induced** (timeout or lifecycle), not a server crash or missing heartbeat.

---

## Existing mitigations (already in codebase)

- **Server**: `main.py` treats connection errors (e.g. `BrokenResourceError`, `ClosedResourceError`) in TaskGroup cleanup as non-fatal and logs a warning; process can exit 0.
- **Server**: `fix_markdown_lint` uses per-file progress and a 15 s heartbeat to reduce idle time on the wire (see `markdown_operations.py`, `docs/mcp-tool-timeouts.md`).
- **Commit workflow**: Commit prompt and docs describe "Connection closed" → retry once → then use documented fallback (e.g. markdown lint via shell) and record "MCP connection closed; fallback used" so the pipeline can continue.
- **Docs**: `docs/mcp-tool-timeouts.md` explains that "Connection closed" usually means client timeout/disconnect, not tool failure, and recommends retry then fallback.

No change to server logic is required for this specific incident; behavior matches the intended design.

---

## Recommendations

1. **Pipeline (already in place)**: On "Connection closed" for `fix_markdown_lint`, retry once; if it fails again (or "tool not found"), run the documented shell fallback and record "MCP connection closed; fallback used". No further server change needed for that.
2. **Client timeout (Cursor)**: If Cursor exposes a configurable timeout for MCP tool calls, consider increasing it for long-running tools (e.g. 2–5 minutes) when the server sends progress; otherwise, relying on retry + fallback is the intended mitigation.
3. **Optional follow-up**: If "Connection closed" during `fix_markdown_lint` remains frequent, consider adding a short note in the commit prompt that the server already uses per-file progress and a 15 s heartbeat, and that -32000 can still occur due to client timeout—retry once then use the documented fallback (see `.cortex/plans/session-optimization-connection-closed-follow-ups-2026-02-03.md`).

---

## References

- Server handling: `src/cortex/main.py` (`_check_connection_error_in_group`, `_handle_connection_error`)
- Progress/heartbeat: `src/cortex/tools/markdown_operations.py` (`_markdown_lint_heartbeat_loop`, `_start_markdown_lint_heartbeat`, `report_progress_safe` after each file)
- Constants: `src/cortex/core/constants.py` (`MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS = 15`)
- Commit prompt: `.cortex/synapse/prompts/commit.md` ("Connection Closed During Long Tool (Retry Then Fallback)")
- Docs: `docs/mcp-tool-timeouts.md`
- Prior investigation: `.cortex/plans/phase-68-investigate-fix-quality-issues-mcp-connection-closed.md`, `.cortex/reviews/session-optimization-2026-02-03T19-57.md`
