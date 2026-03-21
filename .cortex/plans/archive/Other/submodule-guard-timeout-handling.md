---
title: "Handle subprocess.TimeoutExpired in pre_commit_submodule_guard"
component: tools/execution
work_type: fix
status: PENDING
priority: medium
created: 2026-03-21
depends_on: []
---

## Goal

Catch `subprocess.TimeoutExpired` in `pre_commit_submodule_guard.py` so that a slow git command does not abort Phase A with an unhandled exception.

## Context

- **Cortex review REV-2026-03-21-2** (Medium severity): `subprocess.run(..., timeout=...)` at lines 86-100 and 106-120 can raise `subprocess.TimeoutExpired`, which is uncaught.
- **Codex review finding #1 (related)**: Bootstrap/guard resilience gap.
- The guard should fail soft on timeout: log a warning and return an empty report (or a single structured violation indicating timeout).

## Implementation Steps

### Step 1: Add TimeoutExpired handler to `_git_submodule_status_text`

Wrap the `subprocess.run` call with `try/except subprocess.TimeoutExpired`, log a warning, and return `None` (consistent with non-zero return code handling).

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `subprocess.run` in `_git_submodule_status_text` | `pre_commit_submodule_guard.py` | Lines 80-105 |
| `TimeoutExpired` handling patterns | `src/cortex/` | Similar subprocess wrappers |

### Step 2: Add TimeoutExpired handler to `_submodule_porcelain_non_empty`

Same pattern: catch timeout, log warning, return `None` or `False`.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `subprocess.run` in `_submodule_porcelain_non_empty` | `pre_commit_submodule_guard.py` | Lines 105-125 |

### Step 3: Add tests for timeout scenarios

Mock `subprocess.run` to raise `subprocess.TimeoutExpired` and verify the guard returns a safe result without propagating the exception.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Existing submodule guard tests | `tests/` | `test_pre_commit_submodule_guard.py` |

## Dependencies

- None.

## Success Criteria

- `subprocess.TimeoutExpired` is caught in both subprocess call sites.
- Guard returns a safe result (empty violations or structured timeout indicator).
- Logger emits a warning on timeout.
- Tests cover timeout scenario for both functions.
- Quality gate passes.

## Testing Strategy

- Mock `subprocess.run` side_effect=`subprocess.TimeoutExpired(cmd="git", timeout=10)`.
- Verify return value and logger.warning call.
- AAA pattern; target 95% coverage maintained.
