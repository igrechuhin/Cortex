# Session Hang Investigation – 2026-01-30T15-00 (commit after format)

## Context

User reported that an agent session "seemed like hanged" and pointed to transcript `3a897575-01db-4e2a-8608-d70b64475010.txt`. That transcript was analyzed to determine where execution stopped.

## Transcript Summary

- **Session**: Commit workflow (`/cortex/commit`).
- **Flow**:
  - Pre-action: Memory bank read (activeContext, progress, roadmap); tool schemas read.
  - **Step 0** (fix errors): `execute_pre_commit_checks(checks=["fix_errors"], project_root=...)` — **completed** (0 errors, 0 warnings).
  - **Step 1** (formatting): `execute_pre_commit_checks(checks=["format"], project_root=...)` — **called**.
- **Transcript end**: The log ends with `[Tool result] call_mcp_tool` for the format check. There is **no subsequent assistant message or tool call**.

So from the transcript we know:

1. The **format** check tool **did** return (the result marker is present).
2. The next logical step would have been: interpret the format result, mark Step 1 complete, then Step 1.5 (markdown lint), Step 2 (type check), etc.
3. Either the **next** assistant turn never occurred (session/context/UI), or the transcript was cut before it was written.

## Root Cause Analysis

### 1. Most likely: session freeze after tool result

- After `execute_pre_commit_checks(checks=["format"])` returned, the agent would normally summarize the result and call the next step (e.g. markdown lint or type check).
- No such turn appears. From the user's perspective the session "hung" either:
  - **While waiting** for the format result (tool run can be long; see below), or
  - **After** the result came back, with no further agent output (session/context/stdio).

So the hang is likely **after** the format step—either a long format run with no visible progress, or a session/context drop right after the tool result.

### 2. Contributing factor: blocking format step

- `execute_pre_commit_checks` with `checks=["format"]` calls the framework adapter's `format_code()` (e.g. Python: black + isort, Rust: cargo fmt).
- All current adapters implement `format_code()` with **synchronous** `subprocess.run()` and no `asyncio.to_thread()`. So:
  - Format runs on the event loop thread and blocks it for the duration of the formatter (often 10–60+ seconds on a large tree).
  - The MCP tool timeout (e.g. `MCP_TOOL_TIMEOUT_VERY_COMPLEX`) only takes effect at `await` points; it does not interrupt this CPU/blocking work.
- Result: the format step can **feel** like a hang (no progress, no cancellation) even when it eventually completes. Combined with a missing next turn, the experience is "session hung."

### 3. Relation to other hang reports

- **tool-hang-investigation-2026-01-29T00-00.md**: Hang after `fix_markdown_lint`; cause included blocking `Path.rglob()` on the event loop and a possible subsequent stall (e.g. tests or session).
- **session-hang-investigation-2026-01-30T00-00.md**: Hang after Step 4 (tests) when coverage was just below 90%; agent ran raw pytest in a Shell; session ended after Shell result with no follow-up (long run + large output).
- **This transcript**: Hang after Step 1 (format); format tool did return; no assistant turn after that. Same pattern: tool returns, then no next turn (session/context) and/or long blocking format run with no visible progress.

## Recommendations

1. **Run format (and other sync adapter work) off the event loop**  
   Use `asyncio.to_thread()` (or equivalent) when calling adapter methods that use `subprocess.run()` (e.g. `format_code()`, `fix_errors()`). That way:
   - The MCP tool timeout still applies to the overall async call.
   - The event loop stays responsive.
   - Users see less "stuck" behavior during format/fix_errors.

2. **Session/stdio**  
   If "hang" reports continue after format or other pre-commit steps, consider:
   - Cursor/MCP stdio timeouts and whether very long tool runs are being cut or not surfaced.
   - Limiting or summarizing large tool responses so the model reliably gets a bounded response and can produce a next turn.

3. **Commit workflow**  
   No change to commit steps is required for this specific transcript; the flow (Step 0 → Step 1 → …) is correct. The issue is execution environment (blocking adapter + missing next turn), not the workflow order.

## Implementation status

- **Rec 1 (off event loop)** — **Done.** `execute_pre_commit_checks` in `src/cortex/tools/pre_commit_tools.py` now runs `_execute_all_checks` via `await asyncio.to_thread(_execute_all_checks, adapter, ...)`, so all adapter work (format, fix_errors, type_check, quality, tests) runs in a thread pool. Event loop stays responsive; MCP tool timeout still applies. Unit test `test_runs_adapter_checks_off_event_loop_via_to_thread` in `tests/unit/test_pre_commit_tools.py` verifies usage.
- **Rec 2 (session/stdio)** — Deferred. Apply if hang reports continue (Cursor/MCP stdio timeouts; limit/summarize large tool responses).
- **Rec 3 (commit workflow)** — N/A. No change required.

## References

- Transcript: `agent-transcripts/3a897575-01db-4e2a-8608-d70b64475010.txt`
- Related: `.cortex/reviews/tool-hang-investigation-2026-01-29T00-00.md`, `.cortex/reviews/session-hang-investigation-2026-01-30T00-00.md`
- execute_pre_commit_checks / format: `src/cortex/tools/pre_commit_tools.py` (`_process_format_check`, `adapter.format_code()`)
- Adapters (sync `format_code()`): `src/cortex/services/framework_adapters/python_adapter.py`, `rust_adapter.py`, etc.
- MCP stability: `src/cortex/core/mcp_stability.py`, `docs/mcp-tool-timeouts.md`
