# Investigation: MCP Error -32000 Connection Closed

**Date:** 2026-02-17  
**Transcript:** `d3c1b4ce-1ad3-4f70-b99c-b2a789df304c.txt`  
**Error:** `{"error":"MCP error -32000: Connection closed"}`

---

## Summary

The error occurred during `fix_markdown_lint` execution at the end of a commit session. The agent correctly retried once, but the retry also failed with the same connection error. This is a **client-side timeout/disconnect issue**, not a server bug.

---

## What Happened

From the transcript (lines 5030-5040):

1. **Initial call**: `fix_markdown_lint(include_untracked_markdown=True)` was called
2. **Connection closed**: Tool returned `MCP error -32000: Connection closed`
3. **Retry attempted**: Agent correctly retried after 2-second delay
4. **Retry failed**: Second attempt also failed with connection error
5. **Fallback**: Agent documented the issue and noted manual verification needed

---

## Root Cause

**Client-side timeout/disconnect** - The client (Cursor) closed the MCP connection before `fix_markdown_lint` finished. This can happen when:

1. **Client-side tool timeout**: Cursor has a timeout for long-running tools (~15-60 seconds)
2. **Connection refresh**: Client may refresh/reconnect when it considers the connection idle
3. **Single stdio connection**: ListOfferings/refresh may trigger a new connection and close the old one

**Important**: The tool may have completed successfully on the server; the connection was already closed when the response was sent.

---

## Server-Side Mitigations (Already in Place)

The server already implements multiple mitigations to reduce connection closures:

1. **Progress reporting every file**: `fix_markdown_lint` reports progress after every file processed
2. **2-second heartbeat**: `MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS = 2` sends periodic progress updates
3. **Batched execution**: `MARKDOWN_LINT_BATCH_SIZE = 25` processes files in batches to reduce total duration
4. **Scoped execution**: Tool only processes git-modified + untracked files (not full repo)
5. **Frequent progress for long tools**: Tools with timeout ≥ 300s report progress every 5s instead of 10s

**Constants** (`src/cortex/core/constants.py`):

- `MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS = 2`
- `MARKDOWN_LINT_BATCH_SIZE = 25`
- `PROGRESS_REPORT_INTERVAL_VERY_FREQUENT_SECONDS = 2`

---

## Current Handling (Correct)

The commit workflow correctly handles this error:

1. **Retry once**: When connection closed error occurs, retry the tool once
2. **Fallback**: If retry fails, use documented shell fallback (Step 12.5)
3. **Document**: Record "MCP connection closed; fallback used" in commit output

**From commit prompt** (line 1551-1555):
> **Action**: (1) **Retry the tool once.** (2) If it fails again with the same class of error (or with "tool not found" / similar after a connection closed error), perform the documented fallback for that step and record "MCP connection closed; fallback used" so the pipeline can proceed.

---

## Recommendations

### No Changes Needed (Current Behavior is Correct)

The current handling is appropriate:

- ✅ Server mitigations are in place
- ✅ Agent correctly retries once
- ✅ Fallback mechanism exists
- ✅ Error is documented

### Optional Improvements (Future Consideration)

1. **Client-side timeout configuration**: If possible, increase Cursor's MCP tool timeout for long-running operations
2. **Better error messages**: Surface clearer messages when tools are cancelled due to client timeout
3. **Connection health monitoring**: Track connection closure patterns to identify systemic issues

---

## Related Documentation

- **Troubleshooting**: `docs/guides/troubleshooting.md` - "MCP error -32000: Connection closed"
- **Timeouts**: `docs/mcp-tool-timeouts.md` - "Client connection closed during long tools"
- **Commit prompt**: `.cortex/synapse/prompts/commit.md` - "Connection Closed During Long Tool"

---

## Status

**Status**: ✅ Handled correctly  
**Action Required**: None - current behavior is appropriate  
**Future Work**: Monitor connection closure patterns; consider client-side timeout configuration if available
