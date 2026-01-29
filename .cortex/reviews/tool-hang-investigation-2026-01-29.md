# Tool Hang Investigation – 2026-01-29

## Context

User reported that a tool appeared to hang during a `/cortex/commit` run. The agent transcript for that session was analyzed to determine the cause.

## Transcript Summary

- **Session**: Commit workflow (`user-cortex/commit`).
- **Last recorded actions**: Step 12 (final validation gate). The agent ran:
  - `fix_formatting.py`, `check_formatting.py`, `check_types.py`, `check_linting.py`
  - `check_test_naming.py`, `check_file_sizes.py`, `check_function_lengths.py`
  - **`fix_markdown_lint(project_root=..., check_all_files=true, include_untracked_markdown=true)`**
- **Transcript end**: The log ends immediately after `[Tool result] call_mcp_tool` for `fix_markdown_lint`. There is no subsequent assistant message or tool call.

So from the transcript we know:

1. `fix_markdown_lint` **did** return (its result is present).
2. The next logical step would have been: run tests (Step 12), then Step 13 (commit), Step 14 (push).
3. Either the **next** tool call never completed (e.g. tests or another MCP call), or the session ended (e.g. context/UI) right after the last result.

## Root Cause Analysis

### 1. Most likely: next tool call or session freeze

- After `fix_markdown_lint` returned, the agent would typically call `execute_pre_commit_checks(checks=["tests"], ...)` (or equivalent). That call has a 600s timeout.
- If that call was issued but the result never made it back (stdio/MCP stall, Cursor UI freeze, or session cut), the user would see “tool hung” with no further progress.
- **Conclusion**: The hang was likely **after** `fix_markdown_lint`—either the tests step or the surrounding session/stdio layer, not `fix_markdown_lint` itself.

### 2. Contributing factor: long or blocking behavior of `fix_markdown_lint`

Even if the actual hang was later, `fix_markdown_lint` with `check_all_files=true` can still cause long, “stuck”-feeling behavior:

- **Blocking file discovery**: `_get_all_markdown_files()` is declared `async` but uses **synchronous** `Path.rglob(pattern)` with no `await`. So:
  - File discovery runs on the event loop thread and blocks it.
  - `asyncio.timeout(300)` only cancels at `await` points; it does not interrupt this CPU-bound, non-yielding work.
  - On a large tree (many dirs/files), `rglob("**/*.md")` and `rglob("**/*.mdc")` can take tens of seconds with no progress or cancellation.
- **Overall timeout**: The tool is wrapped with `@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_SECONDS)` (300s). So the tool will eventually return or time out, but the user can see a long period with no visible progress.

So `fix_markdown_lint` can **feel** like a hang even when it eventually completes, and in combination with a subsequent stall (tests or session), the user experience is “tool hung.”

## Recommendations

1. **Run file discovery off the event loop**  
   Move `Path.rglob` into a thread (e.g. `asyncio.to_thread`) so:
   - The 300s MCP timeout continues to apply to the overall tool run.
   - The event loop stays responsive and other work can proceed.
   - No new timeout is strictly required for discovery if the outer 300s is acceptable.

2. **Optional: progress or chunking**  
   If needed later, consider reporting progress or processing markdown in chunks so long runs are less opaque.

3. **Session/stdio**  
   If “tool hung” repeats after the next tool (e.g. tests), investigate Cursor/MCP stdio timeouts and whether `execute_pre_commit_checks` for tests is hitting the 600s limit or stalling earlier.

## References

- Transcript: `agent-transcripts/57063e4f-830b-4e0d-9ec4-d6d315ed6151.txt`
- `fix_markdown_lint`: `src/cortex/tools/markdown_operations.py` (`_get_all_markdown_files`, `_fix_markdown_lint_impl`, `@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_SECONDS)`)
- MCP stability: `src/cortex/core/mcp_stability.py` (`with_mcp_stability`, `asyncio.timeout`), `docs/mcp-tool-timeouts.md`
- Phase 57: `.cortex/plans/archive/` is already excluded in `_get_all_markdown_files` to avoid scanning archived plans.
