# Session Optimization: Connection Closed Follow-ups (2026-02-03)

## Status

Status: PENDING

## Source

Created from end-of-session analysis: `.cortex/reviews/session-optimization-2026-02-03T19-57.md`.

## Goal

Implement optional follow-ups from the fix_markdown_lint MCP -32000 Connection closed resolution (2026-02-03): (1) document the new behavior in the commit prompt; (2) consider applying the same progress/heartbeat pattern to other long-running tools if they exhibit connection closed.

## Context

- **Done (2026-02-03)**: fix_markdown_lint now reports progress after every file and runs a 15s heartbeat during long runs to avoid client idle timeout (-32000 Connection closed). See roadmap entry "fix_markdown_lint MCP -32000 Connection closed (2026-02-03)" and docs/mcp-tool-timeouts.md.
- **Optional**: Commit prompt "Connection Closed During Long Tool" / fallback section could note that fix_markdown_lint uses per-file progress and 15s heartbeat; if -32000 still occurs, retry once then use the documented shell fallback.
- **Consider**: If fix_quality_issues or other long tools exhibit -32000 under load, apply the same pattern: per-unit progress where possible + optional time-based heartbeat (e.g. 15s) when a single unit can take a long time.

## Implementation Steps

1. **Optional – Commit prompt note**
   - In the commit prompt (e.g. Step 12.6 or "Connection Closed During Long Tool" / Failure Handling), add one sentence: fix_markdown_lint now uses per-file progress and a 15s heartbeat to reduce connection closed; if -32000 still occurs, retry once then use the documented shell fallback.
   - Verify no duplicate or conflicting wording with existing fallback text.

2. **Consider – Other long tools**
   - If fix_quality_issues or other long-running tools report -32000 in usage/reviews, add a small investigation: measure typical duration and whether progress/heartbeat is present; if needed, add per-unit progress and/or a 15s heartbeat using the same pattern as fix_markdown_lint (MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS or a shared constant).
   - Track outcome in roadmap (e.g. "Long-tool heartbeat for fix_quality_issues" or "No action needed").

## Success Criteria

- Optional: Commit prompt clearly states fix_markdown_lint heartbeat behavior and fallback when -32000 still occurs.
- Consider: Decision recorded (implement heartbeat for tool X, or no action) if/when other long tools show -32000.

## Dependencies

- fix_markdown_lint MCP -32000 fix (2026-02-03) – complete.
- Session optimization review: .cortex/reviews/session-optimization-2026-02-03T19-57.md.
