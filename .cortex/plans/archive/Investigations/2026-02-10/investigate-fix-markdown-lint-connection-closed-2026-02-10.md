# Investigation: fix_markdown_lint Connection Closed (2026-02-10)

## Status

COMPLETE – mitigations applied.

## Summary

`fix_markdown_lint` frequently fails with MCP error -32000 ("Connection closed") during the commit workflow. Logs show **ListOfferings/ListToolsRequest** from Cursor coinciding with the disconnect. Mitigations: shorter heartbeat, batched execution.

## Log Pattern (2026-02-10)

| Time     | Event                                      |
|----------|--------------------------------------------|
| 15:32:10 | fix_markdown_lint called                    |
| 15:32:11 | Progress 0/2                                |
| 15:32:17 | Progress 1/2                                |
| 15:32:20 | **ListOfferings**, ListToolsRequest         |
| 15:32:24 | MCP stdio connection broken; -32000         |

Disconnect occurs ~14 s into the run. The first 15 s heartbeat had not fired; ListOfferings happens shortly before disconnect.

## Root Cause

Client (Cursor) sends ListOfferings while the tool is running. This correlates with connection closure. Likely causes:

1. Client-side tool-call timeout (~15–60 s).
2. Client refresh/reconnect when it considers the connection idle.
3. Single stdio connection – ListOfferings/refresh may trigger a new connection and close the old one.

## Mitigations Applied

1. **Heartbeat 15 s → 5 s** – More frequent progress so the connection has traffic before ListOfferings.
2. **Batched markdownlint** – Process files in batches of 25 instead of one subprocess per file. Fewer invocations and shorter total duration (e.g. 50 files: 2 batches vs 50 subprocesses).
3. **Docs and prompts** – Commit prompt and `docs/mcp-tool-timeouts.md` updated to mention 5 s heartbeat and batching.

## Constants Changed

- `MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS`: 15 → 5  
- `MARKDOWN_LINT_BATCH_SIZE`: 25 (new)

## References

- `src/cortex/core/constants.py` – Heartbeat and batch size
- `src/cortex/tools/markdown_operations.py` – `_run_markdownlint_batch`, `_parse_markdownlint_lines_by_file`
- `docs/mcp-tool-timeouts.md` – Server mitigations
- `.cortex/synapse/prompts/commit.md` – Connection Closed section
- Prior: `.cortex/plans/archive/Investigations/2026-02-07/investigate-mcp-connection-closed-2026-02-07.md`
