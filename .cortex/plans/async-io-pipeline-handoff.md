---
title: "Replace synchronous file I/O with async in pipeline_handoff"
component: core
work_type: fix
status: PENDING
priority: medium
created: 2026-03-21
depends_on: []
---

## Goal

Replace synchronous `write_text()`/`read_text()` calls in the async `pipeline_handoff` MCP tool with `asyncio.to_thread()` to prevent event-loop blocking during pipeline state persistence.

## Context

- Flagged in code review `2026-03-20T15-55` as Medium severity (finding #2).
- `src/cortex/tools/session/pipeline_handoff.py:91-166`: uses `state_file.write_text(...)`, `task_file.write_text(...)`, `task_file.read_text(...)`, `state_file.read_text(...)` synchronously inside async MCP tool handlers.
- The `pre_commit_detached.py` module correctly uses `await asyncio.to_thread(result_path.read_text)` — same pattern should apply here.
- Impact: under load (multiple MCP calls in flight), sync I/O can stall the event loop and cause Cursor connection timeouts.

## Implementation Steps

### Step 1: Wrap write operations in asyncio.to_thread

- **File**: `src/cortex/tools/session/pipeline_handoff.py`
- Replace `state_file.write_text(json_str)` with `await asyncio.to_thread(state_file.write_text, json_str)`
- Same for `task_file.write_text(...)` in the `write_task` operation
- Import `asyncio` if not already imported

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `write_text` calls in pipeline_handoff | `pipeline_handoff.py` | Lines 91-118, 121-141 |
| `asyncio.to_thread` wrapping | Same | Same |

### Step 2: Wrap read operations in asyncio.to_thread

- **File**: `src/cortex/tools/session/pipeline_handoff.py`
- Replace `task_file.read_text()` with `await asyncio.to_thread(task_file.read_text)`
- Same for `state_file.read_text()`

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `read_text` calls in pipeline_handoff | `pipeline_handoff.py` | Lines 144-166 |
| `asyncio.to_thread` wrapping | Same | Same |

### Step 3: Update tests

- **File**: Existing tests for pipeline_handoff
- Verify tests still pass with async file I/O
- Add a test that verifies the operation is non-blocking (mock `asyncio.to_thread` to confirm it's called)

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Pipeline handoff tests | `tests/` | Grep for `pipeline_handoff` |
| `asyncio.to_thread` mock | Test file | Updated tests |

## Dependencies

None.

## Success Criteria

- All file I/O in `pipeline_handoff` uses `asyncio.to_thread()`
- No sync `read_text`/`write_text` in async code paths
- All existing tests pass
- Quality gate passes

## Testing Strategy

- Existing pipeline_handoff tests continue to pass
- Verify async wrapping via mock
- 95%+ coverage maintained
