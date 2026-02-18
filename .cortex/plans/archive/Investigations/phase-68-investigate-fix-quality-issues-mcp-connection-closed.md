## Phase 68: Investigate `fix_quality_issues` MCP connection closed

### Status

- **Status**: COMPLETE (2026-02-18) - Fix applied: timeout increased to 960s, progress reporting enabled
- **Priority**: Blocker (ASAP when reproduces)
- **Created**: 2026-02-03
- **Updated**: 2026-02-18 - Fix completed: `fix_quality_issues` timeout changed to `MCP_TOOL_TIMEOUT_VERY_COMPLEX` (960s) and progress reporting enabled

### Problem Statement

During a `/cortex/commit` run, the `fix_quality_issues` MCP tool failed with:

- Client-side error: `MCP error -32000: Connection closed`
- Server logs (main entry point) reported:
  - `MCP stdio connection broken during TaskGroup cleanup (client disconnected); group_msg=unhandled errors in a TaskGroup sub_count=1 exc_type=BrokenResourceError exc_msg=`

After this event, subsequent `ListOfferings` requests briefly reported `0 tools, 0 prompts, 0 resources` for the `user-cortex` MCP server until the client reinitialized its connection.

### Context

- MCP server entry point: `src/cortex/main.py`
  - Uses `_handle_broken_resource_in_group()` and `_handle_connection_error()` to treat `anyio.BrokenResourceError`, `anyio.ClosedResourceError`, `BrokenPipeError`, and related OS errors as **graceful client disconnects** with exit code `0`.
- MCP stability layer: `src/cortex/core/mcp_stability.py`
  - `mcp_tool_wrapper()` and `with_mcp_stability()` provide:
    - Timeouts via `asyncio.timeout()`
    - Retries and connection health checks
    - Connection error classification via `_is_connection_error()`
    - Usage tracking and optional progress reporting
- `fix_quality_issues` implementation: `src/cortex/tools/pre_commit_tools.py`
  - Decorated with `@mcp.tool(...annotations=...)`, `@ensure_usage_context`, and `@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)`.
  - Internally calls `execute_pre_commit_checks()` (also wrapped) to run `fix_errors`, `format`, and `type_check` without running tests.

### Current Findings (2026-02-03)

- **Reproduction from this session**:
  - `check_mcp_connection_health` MCP tool currently reports a healthy connection with expected semaphore usage.
  - A fresh `fix_quality_issues` call completed successfully:
    - `status="success"`
    - `errors_fixed=0`, `warnings_fixed=0`, `formatting_issues_fixed=0`, `markdown_issues_fixed=0`, `type_errors_fixed=3`
    - `remaining_issues=["3 type errors remain after auto-fix"]`
  - No MCP connection errors were observed during this run; the server remained stable.
- **Interpretation of the failure log**:
  - The `BaseExceptionGroup` handled in `main()` contained `anyio.BrokenResourceError`, which `_handle_broken_resource_in_group()` correctly classifies as a **connection-related** error.
  - The resulting behavior (warning log + `sys.exit(0)`) matches the design for **client-initiated disconnects** (e.g., tool cancelled in the UI, client timeout, or IDE shutdown during a long-running tool).
  - There is no evidence of an internal server bug (e.g., uncaught exception in `fix_quality_issues`, misclassified timeout, or unbounded hang) in the current code.

### Hypothesis

- The observed `MCP error -32000: Connection closed` for `fix_quality_issues` was caused by the **client closing the MCP stdio connection** (likely due to a UI/tool timeout or manual cancellation) while the tool was still running.
- The server’s current behavior—logging the `BrokenResourceError` in TaskGroup cleanup and exiting with code `0`—is **intentional** and consistent with prior phases that hardened connection handling (Phases 19, 32, 34, 36, 46).
- The brief period where `ListOfferings` returned `0 tools` reflects the client-side state after the server exited, before the MCP integration reinitialized the `user-cortex` server.

### Immediate Mitigation

- For the current workspace:
  - The `user-cortex` MCP server is healthy and responsive.
  - `fix_quality_issues` can be called successfully and should be used to keep the workspace clean before further work or commit attempts.
  - Remaining type errors reported by `fix_quality_issues` must be fixed manually and re-validated (type check and quality gates) before any commit.

### Related: fix_markdown_lint (2026-02-03)

The same class of error (`MCP error -32000: Connection closed`) occurred for **fix_markdown_lint** during a commit run: the tool was invoked with `check_all_files=True`, ran ~20s, then the client disconnected and the tool call failed. Server mitigations applied:

- **Initial progress**: Report progress 0% as soon as linting starts so the client sees activity immediately.
- **Faster per-file progress**: Report progress every 3 files (was 5) to reduce the chance of client idle timeout during slow batches.

Commit prompt already documents retry-then-fallback for `fix_markdown_lint` when Connection closed occurs (run markdownlint via shell with same scope).

### Open Questions

1. **Client timeout behavior**:
   - What timeout or cancellation policy is applied by the host IDE for long-running tools like `fix_quality_issues`?
   - Are there scenarios where the client cancels a tool preemptively even though it is still making progress?
2. **Post-disconnect UX**:
   - When a tool is cancelled due to connection closure, can the orchestrator surface a clearer message (e.g., “Tool cancelled by client/timeout, please re-run”) instead of a generic MCP error?
3. **Tool granularity**:
   - Should `fix_quality_issues` be split into smaller, more targeted operations (e.g. “fix types only”, “fix formatting only”) to reduce the chance of hitting client-side limits in large repos?

### Server mitigations (2026-02-03)

To reduce "Connection closed" (-32000) during long tools (e.g. `fix_markdown_lint`, `fix_quality_issues`):

1. **Shorter progress interval for long-running tools**: In `cortex.core.mcp_stability`, when tool timeout ≥ 300s, progress is reported every 5s instead of 10s (`PROGRESS_REPORT_INTERVAL_LONG_RUNNING_SECONDS` in `constants.py`), so the client is less likely to treat the connection as idle.
2. **Per-batch progress in fix_markdown_lint**: `fix_markdown_lint` now reports progress every 5 files while processing, in addition to the time-based progress from the wrapper, so the connection sees activity during long runs. See `docs/mcp-tool-timeouts.md` "Client connection closed during long tools" → "Server-side mitigations".

### Related: Resource read timeouts (-32001) and "unknown message ID"

During the same session you may see `MCP error -32001: Request timed out` on resource reads and `Received a response for an unknown message ID`. These occur when the client fetches many resources in parallel while a long tool (e.g. `rules`) is running: resource requests queue behind the tool, the client times them out and cancels, then the server responds later → client reports "unknown message ID". This is **expected behavior**, not a server bug. See **docs/mcp-tool-timeouts.md** section "Resource read timeouts and unknown message ID" for cause and recommendations (prefer tools over resources during commit; avoid opening resource-heavy UI during long tools).

### Next Steps

1. **Client timeout behavior (tracked separately)**
   - Confirming host IDE tool timeout policies and UX is now tracked in
     `session-optimization-connection-closed-follow-ups.md` and related
     session-optimization plans, rather than this phase.
2. **Improve orchestrator failure handling (COMPLETED)**
   - Commit and implementation prompts now include an explicit
     "Connection Closed During Long Tool (Retry Then Fallback)" section that
     instructs agents to:
     - Retry long-running tools like `fix_quality_issues` once when a
       `Connection closed` / `ClosedResourceError` is reported.
     - Use the documented fallback or stop the commit when the second attempt
       fails, instead of silently proceeding.
3. **Refine `fix_quality_issues` behavior for long-running scenarios (COMPLETED)**
   - `mcp_stability.py` provides time-based progress reporting and connection
     health checks; `fix_quality_issues` is wrapped with `mcp_tool_wrapper` with
     timeout `MCP_TOOL_TIMEOUT_VERY_COMPLEX` (960s) and `enable_progress=True`
     so the client sees regular activity during long runs.
   - Additional granularity (e.g. narrower helpers or per-check tools) is now
     tracked in future optimization phases and is out of scope for this
     connection-closed investigation.
4. **Optional: expose narrower quality helpers (DEFERRED)**
   - Considered but not required to treat `Connection closed` as a
     non-server-bug condition; future work remains in roadmap items focused on
     quality tooling ergonomics rather than connection stability.

### 2026-02-04 Update (Initial)

- Reproduced `MCP error -32000: Connection closed` for `fix_quality_issues` from
  this workspace using the `user-cortex` MCP server while
  `check_mcp_connection_health` reported a healthy connection.
- Confirmed that:
  - Connection-closure errors are classified correctly by `_is_connection_error`
    and handled via `_handle_connection_error` and `_raise_final_error` in
    `mcp_stability.py`.
  - The main entry point treats `anyio.BrokenResourceError` / `ClosedResourceError`
    as graceful client disconnects with exit code `0`, matching the design in
    prior phases.
  - Commit/implementation prompts document the retry-then-fallback strategy so
    that `fix_quality_issues` behaves as a non-blocking helper when the client
    closes the connection.

### 2026-02-04 Update (Root Cause Identified)

**Root Cause**: `fix_quality_issues` uses `MCP_TOOL_TIMEOUT_QUALITY_FIXES` (60 seconds) but internally calls `execute_pre_commit_checks` which can take up to `MCP_TOOL_TIMEOUT_VERY_COMPLEX` (600 seconds). Additionally, progress reporting is enabled but **does not activate** because the 60s timeout is below `PROGRESS_THRESHOLD_TIMEOUT_SECONDS` (120s), causing the client to see no activity and timeout.

**Fix**: Change `fix_quality_issues` timeout from `MCP_TOOL_TIMEOUT_QUALITY_FIXES` (60s) to `MCP_TOOL_TIMEOUT_VERY_COMPLEX` (960s) to match the actual operation duration and enable progress reporting.

**Fix Applied (2026-02-18)**:

- Timeout changed to `MCP_TOOL_TIMEOUT_VERY_COMPLEX` (960s) ✅
- Progress reporting enabled (`enable_progress=True`) ✅
- All tests pass (4244 tests, 91.8% coverage) ✅
- Quality gate passes ✅

### Testing Strategy

- **Coverage target**: Achieve ≥95% coverage for any new or modified logic in `pre_commit_tools.py` (`fix_quality_issues`), `mcp_stability.py` timeout / retry handling, and any updated commit / implementation prompts.
- **Unit tests**:
  - Simulate `fix_quality_issues` runs under:
    - normal completion,
    - connection-closed (`BrokenResourceError` / `ClosedResourceError`),
    - repeated timeout scenarios with retries.
  - Verify progress reporting cadence and that scoped runs (e.g., changed files only) behave correctly and complete within configured timeouts.
  - Assert that timeout / connection errors are classified and surfaced as structured results, not generic failures.
- **Integration tests**:
  - Run `/cortex/commit` and focused quality flows on this repo, validating:
    - retry-then-fallback behavior for `fix_quality_issues` and `fix_markdown_lint`,
    - no “partial proceed” when `fix_quality_issues` times out or the client disconnects.
  - Include tests that exercise large-file / many-file scenarios to ensure the pipeline completes within configured time budgets and that CI remains green.
- **Testing standards**:
  - All tests follow AAA pattern; no blanket skips. Any skip must have explicit justification and a linked ticket.
  - New tests must integrate with existing quality gates (file size, function length, type_check, tests) and keep overall coverage ≥90% while meeting ≥95% for the new work.

### Definition of Done

1. Reproduced or reasonably simulated connection-closed and timeout scenarios for `fix_quality_issues` and confirmed they are handled with clear, user-facing guidance.
2. Commit and implementation prompts explicitly document how to respond when `fix_quality_issues` fails due to connection closure or repeated timeouts (retry, then stop the workflow rather than partially proceeding).
3. No open MCP-tool failure alerts or roadmap blockers remain specifically for `fix_quality_issues` connection-closed or timeout errors.
4. All tests (including any new tests for this behavior) pass, quality gates remain green, and `fix_quality_issues` runs reliably on this repo without hitting client or server timeouts in normal usage.
