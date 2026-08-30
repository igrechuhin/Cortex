---
id: fix-transclusion-resolution-reliability
title: "Fix _execute_transclusion_resolution Reliability (16.6% Error Rate)"
status: PENDING
priority: High
created: 2026-04-03
area: Quality & Reliability Improvements
tags: [transclusion, reliability, error-rate, linking]
---

## Goal

Reduce the error rate of `_execute_transclusion_resolution` from 16.6% (1,062 failures out of 6,415
calls) to below 2%. This is the highest-error-rate tool with significant call volume. Secondary
goal: reduce average token cost from 274 tokens/call by trimming the response payload.

## Context

### Current State

From 418K events over 50 days:

- **6,415 calls** to `_execute_transclusion_resolution`
- **1,062 failures** — 16.6% error rate
- **274 avg tokens/call** — 1,138K total tokens consumed
- `resolve_transclusions_resource` returns **1,633 avg tokens** vs `resolve_transclusions` tool at
  219 avg tokens — a 7.5x discrepancy suggesting the resource path inflates responses

### Code Path

`resolve_transclusions()` → `_resolve_transclusions_run_or_error()` →
`execute_tool_with_stability(_execute_transclusion_resolution, …)` →
`_execute_transclusion_resolution()`:

1. `get_managers(root_path)` — initializes managers (potential failure point if root is wrong)
2. `_validate_transclusion_file()` — checks if file exists in `.cortex/memory-bank/`
3. `fs_manager.read_file(file_path)` — reads original content
4. `_check_no_transclusions()` — early return if no transclusions found
5. `transclusion_engine.resolve_content()` — recursive resolution with `CircularDependencyError` /
   `MaxDepthExceededError` guards
6. `build_transclusion_success_response()` — assembles JSON result

Known error classes:

- `FileNotFoundError` — target file missing from memory-bank
- `CircularDependencyError` — circular `{{include:}}` reference chain
- `MaxDepthExceededError` — nesting deeper than `max_depth` (default 5)
- `ValueError` — section heading not found (`_raise_section_not_found_error`)
- Root resolution failures — `resolve_project_root_async()` returns wrong path in Cursor
- Manager initialization errors from `get_managers(root_path)`

The `resolve_transclusions_resource` path wraps the tool via `@mcp_resource_wrapper` which returns
the same JSON but the token discrepancy (1,633 vs 219) suggests the resource path may be returning
`original_content` + `resolved_content` together where the tool path does not, or the response
structure differs.

## Implementation Steps

### Step 1 — Instrument failure categories

Add failure-category counters to `_execute_transclusion_resolution` so errors can be broken down by
class (FileNotFoundError, CircularDependencyError, MaxDepthExceededError, ValueError, other).
Emit structured log entries with `error_type`, `file_name`, and `root` fields at `WARNING` level so
they appear in usage-event analysis.

- File: `src/cortex/tools/linking/transclusion_operations.py`
- Approach: wrap the try/except in `_resolve_transclusions_run_or_error` to log error category
  before calling `resolve_transclusions_error_json`

### Step 2 — Harden root resolution for transclusions

The `resolve_project_root_async(None, ctx)` call in `resolve_transclusions()` is a known source of
failures (wrong root when Cursor strips args). Add a fallback: if `resolve_project_root_async`
returns a path that does not contain `.cortex/memory-bank/`, attempt to fall back to
`get_current_project_root()` before failing.

- File: `src/cortex/tools/linking/transclusion_operations.py`
- Pattern: same root-resolution hardening used in other tools (`get_current_project_root() or
  Path(await get_or_resolve_project_root(ctx))`)

### Step 3 — Defensive validation in `_validate_transclusion_file`

Currently returns an error model for missing files but does not check whether the file name
contains path traversal or unsupported characters beyond what `construct_safe_path` checks. Verify
that the error model returned for `ValueError` and `PermissionError` is always populated with
`error_type` and `message` fields so callers can distinguish path-safety errors from not-found
errors.

- File: `src/cortex/tools/linking/transclusion_operations.py`
- Ensure `ResolveTransclusionsErrorResult` carries `error_type` field set to `"PathError"` for
  path-safety failures vs `"FileNotFoundError"` for missing files.

### Step 4 — Fix section-not-found to return graceful fallback instead of raising

`TransclusionEngine._raise_section_not_found_error` raises `ValueError` which gets caught by the
generic `except Exception as e` in `_resolve_single_transclusion` and replaced with an HTML
comment `<!-- TRANSCLUSION ERROR: ... -->`. This silently degrades but contributes to the error
count. Change behavior to fall back to full-file content when section is not found (matching
documented behavior in the docstring: "Missing section references will include the entire file as
fallback"), and emit a structured warning instead of raising.

- File: `src/cortex/linking/transclusion_engine.py`
- Method: `_apply_section_filter` — catch `ValueError` from `extract_section`, log warning,
  return full content
- Verify docstring matches new behavior

### Step 5 — Reduce resource vs tool token discrepancy

`resolve_transclusions_resource` calls `resolve_transclusions(file_name=file_name, max_depth=5)`
which returns the full JSON including both `original_content` and `resolved_content`. For the
resource path, `original_content` is rarely needed. Add an optional `include_original` flag
(default `False`) to the resource path so it only returns `resolved_content` by default, reducing
average resource response size from 1,633 to ~400 tokens.

- File: `src/cortex/tools/linking/transclusion_operations.py`
- Only changes the resource function `resolve_transclusions_resource`; the tool function is
  unchanged

### Step 6 — Add regression tests for each error category

Write or extend tests in the test suite covering:

- `FileNotFoundError` → expect `status: "error"`, `error_type: "FileNotFoundError"`
- `CircularDependencyError` → expect `status: "error"`, `error_type: "CircularDependencyError"`
- `MaxDepthExceededError` → expect `status: "error"`, `error_type: "MaxDepthExceededError"`
- Section-not-found → expect graceful full-file fallback, no error status
- Wrong root path → expect error with `error_type` set, not unhandled exception

### Step 7 — Run quality gate and verify

After implementing all changes, run `run_quality_gate()` to confirm 0 regressions. Verify via
structured logs in the next usage-event batch that the error rate has dropped.

## Verification Checklist

- [ ] `_execute_transclusion_resolution` error rate measured via structured logs (Step 1)
- [ ] Root resolution fallback implemented and covered by test (Step 2)
- [ ] `ResolveTransclusionsErrorResult` carries `error_type` for all error paths (Step 3)
- [ ] Section-not-found returns full-file content instead of raising (Step 4)
- [ ] Resource path drops `original_content` by default (Step 5)
- [ ] New regression tests pass (Step 6)
- [ ] `run_quality_gate()` passes with 0 new failures (Step 7)

## Dependencies

- `src/cortex/tools/linking/transclusion_operations.py`
- `src/cortex/linking/transclusion_engine.py`
- `src/cortex/tools/context/load_auxiliary_models.py` (ResolveTransclusionsResult /
  ResolveTransclusionsErrorResult models)
- `src/cortex/tools/linking/transclusion_response_helpers.py`
- `src/cortex/core/project_root_resolver.py`

## Success Criteria

1. Error rate for `_execute_transclusion_resolution` drops from 16.6% to < 2% within next 50-day
   measurement window
2. `resolve_transclusions_resource` avg token response drops from 1,633 to < 500
3. All regression tests green; quality gate passes
4. No new unhandled exceptions in transclusion code paths

## Testing Strategy

- Unit tests: mock `FileSystemManager`, `LinkParser`, `TransclusionEngine` to inject each error
  class and assert correct response shape
- Integration test: call `resolve_transclusions` via MCP on a real file with a missing include
  target; assert graceful JSON error response rather than exception propagation
- Regression: run full test suite via `run_quality_gate()` after each step

## Partial Progress Log

- 2026-04-03: Steps 1–3 (partial): structured JSON warning logs on exceptions in
  `_resolve_transclusions_run_or_error`; memory-bank root fallback when
  `resolve_project_root_async` returns a path without `.cortex/memory-bank`;
  `error_type` PathError / FileNotFoundError on validation errors; root-fallback
  regression test — files: `src/cortex/tools/linking/transclusion_operations.py`,
  `tests/tools/test_linking_operations.py`, `tests/unit/test_pre_commit_tools.py`
  (structural test helpers only)

- 2026-04-03: Steps 4–5 — `_apply_section_filter` catches missing section headings and
  returns full target file with `transclusion_section_not_found_fallback` warning;
  `_run_resolve_transclusions_pipeline` / resource path omit `original_content` from
  JSON by default — files: `src/cortex/linking/transclusion_engine.py`,
  `src/cortex/tools/linking/transclusion_operations.py`,
  `tests/unit/test_transclusion_engine.py`, `tests/tools/test_linking_operations.py`
