# Code Review Report

**Date:** 2026-03-13  
**Scope:** Recently changed source and tests (from `git diff --name-only`):  
`src/cortex/tools/execution/pre_commit_detached.py`, `pre_commit_status.py`, `src/cortex/tools/plans/plan.py`, `tests/tools/test_plan_completion.py`, and related unit tests.

---

## Summary

| Metric | Score | Evidence |
|--------|-------|----------|
| Architecture | 7 | Clear layering: execution (detached worker, status summarizer), plans (dispatch + CRUD/complete/register). plan.py is a thin dispatcher; pre_commit_detached/status separate process lifecycle from result summarization. Minor: some inline imports in plan.py for error models. |
| Test Coverage | 7 | 48 tests pass for pre_commit_detached, pre_commit_status, plan completion. test_plan_completion.py: roadmap bullet removal, Completed Work section, progress/activeContext append, date validation, archive/path traversal, integration and plan tool smoke. test_pre_commit_status.py: no_runs, completed/running/error/timeout/queued, checks_summary, get_pre_commit_status_impl by job_id. test_pre_commit_detached.py covers hash, find_existing_result, spawn, poll. Edge cases (first match wins, duplicate skip, path traversal) covered. |
| Documentation | 6 | Module docstrings present in all three modules. plan() tool docstring has USE WHEN and EXAMPLES. Inline comments for constants (_RESULT_FRESHNESS_SECONDS, _POLL_INTERVAL_SECONDS). No high-level design doc for detached pipeline in repo. |
| Code Style | 8 | execute_pre_commit_checks(quality): "All checks passed". Ruff/black clean. Consistent naming (snake_case, _private helpers), type hints throughout. Literal for PreCommitJobStatus; Pydantic for result models. |
| Error Handling | 8 | Structured: JSON decode/OSError caught in _read_result_file, find_existing_result; explicit error dicts (_worker_died_error, _timeout_error, _already_running_error). plan.py returns Pydantic model_dump_json() for invalid operation/missing params. PreCommitRunSummary carries error message. No bare except. |
| Performance | 7 | Polling every 2s with bounded heartbeat count. Result files keyed by args hash; no unbounded scans in hot path. _iter_result_files sorts by mtime (single dir listing). No obvious O(n²) or blocking I/O in async paths (read_text in poll loop is quick). |
| Security | 8 | No hardcoded secrets in scope. test_plan_completion.py includes test_rejects_path_traversal_in_plan_file_name. Inputs from result JSON validated with isinstance. Log paths and result paths under project .cortex/.session. |
| Maintainability | 7 | pre_commit_detached ~398 lines, plan.py ~253; functions generally short. Duplication: _session_dir defined in both pre_commit_detached and pre_commit_status (could be shared). Clear function names and single-purpose helpers. |
| Rules Compliance | 8 | type_check and quality checks passed (execute_pre_commit_checks). No file/function length violations reported. Pydantic used for result shapes; Literal for external API (PreCommitJobStatus). |

**Overall score (average):** **7.3 / 10**

---

## Issues

| Severity | Location | Description / Suggestion |
|----------|----------|---------------------------|
| Low | pre_commit_detached.py, pre_commit_status.py | **Duplicate _session_dir**: Same logic `project_root / ".cortex" / ".session"` and `d.mkdir(parents=True, exist_ok=True)` in both modules. Consider moving to a shared helper (e.g. cortex.tools.execution.session_paths or similar) to avoid drift. |
| Low | pre_commit_detached.py:144–151 | **Log file handle in _spawn_detached_process**: The process is started with `stdout=lf, stderr=lf` inside `with open(log_file, "w") as lf`. When the `with` block exits, the parent closes the file; the child retains the fd on Unix, so behavior is correct. Optional: add a one-line comment that the child keeps the fd so the log stays open. |
| Low | plan.py:129–130, 144–145 | **Assert after guard**: `assert plan_title is not None and summary is not None` (and similar for register) are redundant after the `if not plan_title or not summary` return. Type narrowers could rely on the early return; the assert is defensive. Consider removing or documenting as invariant check for clarity. |

---

## Static Analysis (Step 5)

- **type_check:** Passed (execute_pre_commit_checks(checks=["type_check"]) — no errors or warnings for src, tests, synapse scripts).
- **quality:** Passed (execute_pre_commit_checks(checks=["quality"]) — "All checks passed", no file/function length violations).

---

## Bug Detection (Step 6)

- No unguarded `None` in critical paths; optional values checked with `is not None` or `isinstance`.
- No mutable default arguments in reviewed code; `summary: dict[str, bool] = {}` in pre_commit_status.py is a local variable in _build_checks_summary, not a default parameter.
- No bare `except:`; catches use `(json.JSONDecodeError, OSError)` or specific error handling.
- Async used correctly (async def, await in poll loop and MCP tool handlers).
- Resources: result files read via Path.read_text() in try/except; log file opened in context manager. Subprocess started with start_new_session=True and DEVNULL stdin; no resource leak identified.

---

## Consistency (Step 7)

- Naming: snake_case, _prefix for private helpers, consistent use of args_hash/session_dir/result_path.
- Error handling: dict with "status"/"error" or Pydantic model_dump_json() for tool responses.
- plan.py follows Phase 50–style operation dispatch (create/list/get/complete/register) consistent with query_memory_bank/query_usage.

---

## Completeness (Step 9)

- No TODO/FIXME/HACK in the reviewed source files (only in validation/operations.py, out of scope).
- Placeholders: None. Optional progress (report_progress_safe) and ctx parameters documented or used.

---

## Test Coverage (Step 10)

- test_plan_completion.py: complete_plan (roadmap, activeContext, progress, archive, path traversal, date validation), update_memory_bank (progress_append, active_context_append), CompletePlanResult serialization, plan(operation="complete") smoke.
- test_pre_commit_status.py: get_last_pre_commit_status_impl and get_pre_commit_status_impl for no_runs, completed, running, error, timeout, queued, and MCP tool wrapper.
- test_pre_commit_detached.py: compute_args_hash, find_existing_result, spawn_detached_worker, poll/interpret.
- AAA pattern and tmp_path fixtures used; Pydantic v2 and JSON parsing validated in tests.

---

## Security (Step 11)

- No hardcoded secrets or sensitive data in logs in the reviewed modules.
- Path traversal test in test_plan_completion (plan_file_name="session-optimization/../evil.md").
- Result and log paths constrained to project_root/.cortex/.session; no user-controlled paths used as-is for sensitive operations.

---

## Performance (Step 12)

- Poll interval and heartbeat total are constants; no unbounded loops without timeout (deadline in poll_for_result).
- I/O in poll loop is single small read_text per iteration; acceptable for 2s interval.
- _iter_result_files does one iterdir and sort; no nested scans in scope.
