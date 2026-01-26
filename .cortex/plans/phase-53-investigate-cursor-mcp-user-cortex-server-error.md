# Phase 53: Investigate Cursor MCP `user-cortex` Server Error

## Summary

The Cursor MCP server `user-cortex` was observed in an errored state where Cursor reported:

- `The MCP server errored. If you definitely need to use this tool ... check the MCP status in Cursor Settings`

This blocks the `/cortex/commit` pipeline because it **requires Cortex MCP tools**:

- `execute_pre_commit_checks()`
- `fix_markdown_lint()`
- `manage_file()`
- `validate()`

## Resolution (2026-01-25)

The server can recover (descriptors reappear) after restart/re-enable in Cursor, but the failure was observed to recur.

### Likely Root Cause: stdout logging breaks MCP stdio

When running as an MCP server over stdio, **stdout must be reserved exclusively for the MCP protocol**. If any library configures the **root logger** with a handler that writes to stdout (commonly `RichHandler`), and the `cortex` logger propagates messages to root, then normal log lines can leak to stdout and break the protocol. Cursor then marks the MCP server as errored and removes tool descriptors (`tools/` disappears).

**Fix applied in repo**:

- `src/cortex/core/logging_config.py`: set `logger.propagate = False` in `setup_logging()` to prevent propagation to root handlers.

### Verification (when server is up)

Verified end-to-end (when recovered) via:

- `check_mcp_connection_health()` returns `healthy: true`
- `get_memory_bank_stats()` returns successfully
- `manage_file(operation="read", file_name="roadmap.md")` succeeds
- `execute_pre_commit_checks(checks=["quality"])` is callable (it may still report repo quality violations, but the MCP tool call itself works)

## Impact

- Commit workflow is **blocked at Step 0** (cannot run `execute_pre_commit_checks`).
- Memory bank operations via `manage_file()` are **unavailable**.
- Any workflow relying on Cortex MCP tools is **unavailable** from Cursor.

## Evidence

- Descriptor root exists: `.cursor/projects/Users-i-grechukhin-Repo-Cortex/mcps/user-cortex/`
- During the failure, the `tools/` directory (and sometimes `prompts/`) appeared missing and calls failed with “tool not found”.
- Current state (recovered): both `tools/` and `prompts/` directories exist, and MCP calls succeed.

## Hypotheses

- Cursor MCP server process crashed and the descriptor cache was truncated.
- Cursor failed to refresh tool descriptors after server restart.
- Local environment / python runtime issue prevents server from launching.
- Recent workspace changes caused runtime import errors during tool registration.

## Reproduction Steps

1. In Cursor, run `/cortex/commit`.
2. Observe the tool call failures with “tool not found”.
3. Check Cursor Settings → MCP for `user-cortex` server errors and logs.

## Investigation Steps

1. **Cursor Settings → MCP**:
   - Confirm `user-cortex` server status and error logs.
   - Restart / re-enable the server.
2. Verify descriptor regeneration:
   - Ensure `.cursor/projects/Users-i-grechukhin-Repo-Cortex/mcps/user-cortex/tools/` is recreated.
3. If server crashes on startup:
   - Capture the crash log (stack trace) from Cursor MCP settings.
   - Identify the import/module causing tool registration failure.
   - Check for **stdout logging** or any non-protocol output before MCP handshake.
4. Once restored:
   - Re-run `/cortex/commit` from Step 0.
5. Quick verification after restart:
   - `check_mcp_connection_health()` should be healthy
   - `manage_file(operation="metadata", file_name="roadmap.md")` should succeed

## Exit Criteria

- `user-cortex` MCP server is running.
- Descriptor directories exist:
  - `.../mcps/user-cortex/tools/`
  - `.../mcps/user-cortex/prompts/` (if applicable)
- Cortex tool calls succeed again (e.g., `manage_file(operation="metadata")`).
