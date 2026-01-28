# Phase 59: Investigate `fix_markdown_lint` MCP Connection Closed Failure

**Status**: IN PROGRESS  
**Priority**: FIX-ASAP (Commit pipeline blocker)  
**Created**: 2026-01-28  
**Related**: Phase 57 (`fix_markdown_lint` timeout), Phase 58 (`execute_pre_commit_checks` timeout stability)

## Goal

Restore reliable markdown lint fixing via the `fix_markdown_lint` MCP tool, so the `/commit` pipeline can complete with **zero markdown lint errors** across **all** markdown files (CI parity).

## Problem Statement

During commit Step 1.5, the tool call:

- `fix_markdown_lint(check_all_files=True, include_untracked_markdown=True)`

failed with:

- `{"error":"MCP error -32000: Connection closed"}`

This blocks the commit pipeline (no fallbacks allowed on MCP tool failure).

## Observations

- The Cortex MCP server process appears to have exited/crashed shortly after the call (no running `src/cortex/main.py` process was detected immediately after the failure).
- The repo already tracks a known performance issue for `fix_markdown_lint(check_all_files=True)` in Phase 57 (archived plans scanning can cause long runtimes/timeouts). This failure mode is different (hard connection close), but could share the same root cause (resource exhaustion / crash).

## Hypotheses

- **Server crash due to unhandled exception** inside markdown lint implementation (e.g., subprocess failure, JSON parsing, path handling).
- **Resource exhaustion** (memory / file handle / process limits) when enumerating all markdown files.
- **Timeout/TaskGroup cancellation bug** leading to server shutdown rather than a clean JSON error response.
- **Large-scope scan** still includes heavy directories (e.g., `.cortex/plans/archive/`) despite prior mitigation work (Phase 57), causing pathological runtime.

## Investigation Steps

1. **Reproduce locally**:
   - Start Cortex MCP server and call `fix_markdown_lint(check_all_files=True)` in isolation.
   - Confirm whether the server disconnects consistently or intermittently.

2. **Capture server logs/traceback**:
   - Run the server with debug logging enabled (or inspect Cursor/MCP logs) to find the exception that triggers shutdown.

3. **Validate directory exclusions**:
   - Confirm `fix_markdown_lint` “all files” scan excludes heavy directories (must at least exclude `.git/`, `node_modules/`, virtualenvs, and `.cortex/plans/archive/` per Phase 57 intent).

4. **Add crash-proof error handling**:
   - Ensure any exception is caught and returned as a structured JSON error (no process exit).
   - Add structured timeout handling that returns JSON rather than closing the connection.

5. **Add/extend tests**:
   - Unit tests that `fix_markdown_lint(check_all_files=True)`:
     - returns `success=false` with `error_message` on controlled failures
     - does not crash/exit the server wrapper
   - Regression test for Phase 57: archived plans exclusion is honored.

## Success Criteria

- `fix_markdown_lint(check_all_files=True, include_untracked_markdown=True)` returns a normal JSON response:
  - `success: true`
  - `files_with_errors: 0`
  - `error_message: null`
- Cortex MCP server remains connected/stable after the call (no -32000 disconnect).
- `/commit` pipeline can proceed past Step 1.5 and complete Step 14.
