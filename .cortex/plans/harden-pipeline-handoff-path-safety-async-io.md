---
title: "Harden pipeline_handoff path safety & async IO"
component: "cortex/session/pipeline-handoff"
work_type: "fix"
status: "PENDING"
priority: "High"
created: "2026-03-20"
execution_order: 1
depends_on: []
---

## Harden pipeline_handoff path safety & async IO

**Status**: PENDING
**Priority**: High
**Complexity**: Medium
**Category**: Fix / Security / Reliability

## Goal
Prevent unsafe filesystem path construction and reduce event-loop blocking in the MCP `pipeline_handoff` tool, while tightening error handling and improving diagnosability in adjacent commit-phase infrastructure (as identified by the code review report `code-review-report-2026-03-20T15-55.md`).

## Context
Code review found:
- High severity security risk: `src/cortex/tools/session/pipeline_handoff.py` builds filesystem paths directly from `pipeline` and `phase` strings without validation/sanitization.
- Medium reliability/performance risk: async tool uses synchronous `read_text`/`write_text` in multiple codepaths.
- Medium maintainability risk: broad `except Exception` blocks in `src/cortex/tools/execution/pre_commit_tools.py`.
- Low diagnosability risk: best-effort init catches `Exception` in `src/cortex/core/container.py` may omit stack traces.

## Implementation Steps

### Step 1: Validate/sanitize `pipeline` and `phase` before path usage
**File**: `src/cortex/tools/session/pipeline_handoff.py`

Implement a safe-name strategy or whitelist validation so `pipeline` and `phase` cannot introduce path separators (`/`, `\\`) or `..` components.

- Define a helper like `_validate_safe_token(token: str, name: str) -> str` or a sanitization function that only permits `[A-Za-z0-9_-]` (replace others with `_`).
- Use the validated/sanitized values inside `_pipeline_dir`, `_task_path`, and `_result_path`.
- On invalid input, return a structured `{"status":"error", ...}` JSON response with a clear message.

### Step 2: Replace synchronous filesystem I/O inside async `pipeline_handoff`
**File**: `src/cortex/tools/session/pipeline_handoff.py`

- Move blocking calls to a thread with `await asyncio.to_thread(...)` for `*_path.write_text(...)` and `*_path.read_text(...)`.
- Ensure the behavior/output JSON shape is unchanged.

### Step 3: Narrow exception handling in pre-commit tool execution
**File**: `src/cortex/tools/execution/pre_commit_tools.py`

- In the two locations highlighted by the review report (fix-quality mode and standard-checks mode), narrow broad `except Exception` handling where possible.
- Preserve the existing error payload/contract shape, but ensure unexpected exceptions are not silently converted into generic errors without adequate context.

### Step 4: Improve diagnosability of best-effort init catches
**File**: `src/cortex/core/container.py`

- In `_post_init_setup`, replace/adjust `except Exception as e:` blocks to catch specific exception types.
- When logging the caught exception, ensure stack traces are preserved (`exc_info=True`) where appropriate.

### Step 5: Add/extend tests for path safety and error contracts
**Files (existing)**:
- `tests/tools/test_pipeline_handoff.py`

Add tests that:
- Attempt `pipeline` with `../` and/or path separators and assert the tool returns `{"status":"error"}` and does not create directories outside the temporary root.
- Attempt `phase` with path separators and assert the same.
- Keep existing success tests unchanged.

For async I/O refactor:
- Add a test that mocks `asyncio.to_thread` (or the underlying blocking calls) to ensure the codepath uses the async-safe mechanism.

## Verification Checklist

### Step 1: Path validation/sanitization
- What to search for | Search scope | Files to re-read
- `pipeline` / `phase` used in filesystem path builders | `src/cortex/tools/session/pipeline_handoff.py` | `pipeline_handoff.py`
- helper/validation function returns safe token | `pipeline_handoff.py` | `pipeline_handoff.py`
- error response for invalid token | tests scope | `tests/tools/test_pipeline_handoff.py`

### Step 2: Async file I/O
- What to search for | Search scope | Files to re-read
- `write_text(` / `read_text(` called directly in async tool paths | `pipeline_handoff.py` | `pipeline_handoff.py`
- use of `asyncio.to_thread` for blocking FS operations | `pipeline_handoff.py` | `pipeline_handoff.py`

### Step 3: Exception narrowing
- What to search for | Search scope | Files to re-read
- remaining `except Exception` blocks in highlighted functions | `pre_commit_tools.py` | `src/cortex/tools/execution/pre_commit_tools.py`

### Step 4: Container init diagnosability
- What to search for | Search scope | Files to re-read
- `logger.*` calls include `exc_info` for the caught exception | `container.py` | `src/cortex/core/container.py`

### Step 5: Tests
- What to search for | Search scope | Files to re-read
- new tests for invalid `pipeline`/`phase` | `tests/tools/test_pipeline_handoff.py` | that file
- test for async-to-thread usage (mock-based) | `tests/tools/test_pipeline_handoff.py` | that file

## Dependencies
- None, but tests must align with the current `pipeline_handoff` response JSON contract.

## Success Criteria
- `pipeline_handoff` rejects or sanitizes unsafe `pipeline`/`phase` values and cannot write outside the expected `.cortex/.session/{session_id}/{pipeline}/` subtree.
- Async toolpaths no longer perform synchronous `read_text`/`write_text` directly.
- Error handling remains contract-compatible for callers.
- Tests pass, including new negative cases for path traversal attempts.
- Coverage for changed areas meets the 95%+ target in the affected test modules.

## Testing Strategy
- Unit tests: extend `tests/tools/test_pipeline_handoff.py` for path validation and error response shape.
- Mocking: use `pytest` + monkeypatch/patch to validate async-to-thread usage without relying on timing.
- Quality gate: run repo-wide Phase A quality gate (tests + type/lint/format) and ensure it stays green.
