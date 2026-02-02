# Make fix_markdown_lint Report Progress Like Tests Tool

## Status

Status: PENDING

## Goal

Make `fix_markdown_lint` report progress the same way as the tests tool: **actual and processed number of files** via MCP progress, **without** fake time-based progress.

## Context

### Current behavior

- **Tests tool** (`execute_pre_commit_checks` when tests run): Uses `_make_test_progress_callback(ctx, loop)` which calls `report_progress_safe(ctx, float(completed), float(total))` so the client sees real counts (e.g. 5 of 10 tests). Time-based progress is not used for this tool.
- **fix_markdown_lint**: Only logs "fix_markdown_lint: starting" and "fix_markdown_lint: completed". It has no per-file progress. Phase 46 added optional time-based progress for long-running tools; `fix_markdown_lint` uses `MCP_TOOL_TIMEOUT_VERY_COMPLEX`, so the wrapper can run a time-based progress loop (fake progress by time), which the user does not want.

### User requirement

Report **actual and processed number of files** (e.g. "3 of 12 files") during the run, and **do not** use time-based/fake progress for this tool.

### Relevant code

- Progress reporting: `cortex.core.context_logging.report_progress_safe(ctx, progress, total)` — same API used by the tests callback.
- Tests callback pattern: `pre_commit_tools._make_test_progress_callback` → `report_progress_safe(ctx, float(completed), float(total))`; callback is passed into the sync pipeline and invoked from the test runner with (tests_done, total_tests).
- fix_markdown_lint flow: `fix_markdown_lint` → `_fix_markdown_lint_run_or_error` → `_fix_markdown_lint_impl` → `_run_markdownlint_with_cache` → `_run_markdownlint_for_files` → `_process_markdown_files_sequential`. The sequential loop processes one file at a time; we can report (processed, total) after each file.
- Wrapper: `mcp_tool_wrapper(timeout=..., enable_progress=None)` auto-enables time-based progress when timeout ≥ 120s. For fix_markdown_lint we want `enable_progress=False` so only file-count progress is used.

## Approach

1. **Thread `ctx` through the impl** so progress can be reported from the sequential processing loop.
2. **Report (processed, total) files** from `_process_markdown_files_sequential` (or a thin wrapper) using `report_progress_safe(ctx, float(processed), float(total))` after each file, matching the tests-tool pattern.
3. **Disable time-based progress** for `fix_markdown_lint` by passing `enable_progress=False` to `mcp_tool_wrapper`, so the wrapper does not run the fake time-based progress loop.

## Implementation Steps

1. **Pass `ctx` through the impl chain**  
   - Add optional `ctx: MCPContext | None = None` to `_fix_markdown_lint_impl`, `_run_markdownlint_with_cache`, `_run_markdownlint_for_files`, and `_process_markdown_files_sequential`.  
   - Ensure `fix_markdown_lint` passes `ctx` from the tool handler into `_fix_markdown_lint_run_or_error` and thus into the impl.

2. **Report file-count progress in the sequential loop**  
   - In `_process_markdown_files_sequential`, after each file is processed (and result appended), call `await report_progress_safe(ctx, float(len(results)), float(total))` where `total = len(files)`.  
   - Optionally report once at start: `await report_progress_safe(ctx, 0.0, float(total))` when `total > 0` and `ctx is not None`.  
   - Use the same signature as the tests tool: `report_progress_safe(ctx, progress, total)` with raw counts (no percentage conversion).  
   - When `ctx is None`, do not call `report_progress_safe` (no-op in tests/non-request code).

3. **Disable time-based progress for fix_markdown_lint**  
   - In the `fix_markdown_lint` tool decorator, set `@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX, enable_progress=False)` so the wrapper does not start the time-based progress loop. File-count progress remains the only progress for this tool.

4. **Tests**  
   - Unit test(s) that when `ctx` is provided, `report_progress_safe` is called with `(processed, total)` after each processed file (e.g. 1/N, 2/N, ..., N/N), and optionally 0/N at start.  
   - Unit test that when `ctx` is None, `report_progress_safe` is never called (or only assert no progress in impl when ctx is None).  
   - Confirm `fix_markdown_lint` is decorated with `enable_progress=False` (e.g. in test_mcp_stability_timeouts or a dedicated test).

## Technical Design

- **Progress API**: Use existing `report_progress_safe(ctx, progress: float, total: float | None)`. For file counts we pass `(processed, total)` as two floats, matching the tests tool.
- **Place of reporting**: Inside `_process_markdown_files_sequential`, after each file is processed (and result appended). Total = `len(files)`; processed = `len(results)`.
- **No new dependencies**: Use `cortex.core.context_logging.report_progress_safe`; no new modules required. Markdown module already imports context_logging for `log_client`.

## Testing Strategy

- **Coverage target**: Minimum 95% for any new branches (progress reporting path, ctx None path).
- **Unit tests**: (1) fix_markdown_lint progress: mock or spy `report_progress_safe`; run impl with small file list and assert calls with (0, N), (1, N), ..., (N, N) or equivalent. (2) When ctx is None, assert no progress calls. (3) Verify `mcp_tool_wrapper(..., enable_progress=False)` for fix_markdown_lint (existing timeout test file or new test).
- **Integration (optional)**: Run fix_markdown_lint with 2–3 markdown files and ctx present; assert progress messages or progress callback invocations in test client.
- **Regression**: Existing fix_markdown_lint tests (success, error, dry_run, check_all_files) still pass; no change to JSON result shape.

## Dependencies

- Phase 46 (progress reporting) — complete; `report_progress_safe` and `mcp_tool_wrapper(enable_progress=...)` exist.
- No blocking dependency on Phase 59 (connection closed) or Phase 57 (timeout); this plan only adds progress reporting and disables time-based progress for this tool.

## Success Criteria

- When `fix_markdown_lint` runs with `ctx` present, the client sees progress as (processed, total) file counts (e.g. 3 of 12 files).
- No time-based progress loop runs for `fix_markdown_lint` (enable_progress=False).
- When `ctx` is None (e.g. tests), no progress is reported and behavior is unchanged.
- All existing fix_markdown_lint and markdown_operations tests pass; new unit tests cover progress reporting and enable_progress=False.

## Risks & Mitigation

- **Over-reporting**: Reporting after every file could be noisy for large N. Mitigation: Keep same pattern as tests tool (every unit); clients can throttle display. If needed later, add reporting every K files.
- **Total vs. files_to_lint**: Total must be the number of files actually processed in the loop (len(files) in _process_markdown_files_sequential). Skipped (non-existing) files still increment results (error_result), so processed count matches len(results); total = len(files) is correct.

## Timeline

Single small change set: impl + tests, 1 session.

## Notes

- Aligning with the tests tool avoids a second progress style and satisfies "actual and processed number of files without fake time-based progress."
- If the MCP client displays progress as "progress / total", the same (processed, total) convention as tests will show "e.g. 5 / 10" for files.
