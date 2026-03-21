---
title: "Deduplicate _session_dir helper across pre-commit modules"
component: tools/execution
work_type: refactoring
status: PENDING
priority: low
created: 2026-03-21
depends_on: []
---

## Goal

Extract the duplicated `_session_dir` function from `pre_commit_detached.py` and `pre_commit_status.py` into a shared module to eliminate drift risk.

## Context

- **Cortex review REV-2026-03-13-1** (Low severity, carried): Both files contain identical `_session_dir(project_root)` implementations.
- **Codex review finding #3 (improvement suggestion #3)**: Deduplicate into a shared `session_paths.py`.

## Implementation Steps

### Step 1: Create shared session_paths module

Create `src/cortex/tools/execution/session_paths.py` with a single public function `session_dir(project_root: Path) -> Path`.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `_session_dir` definition | `src/cortex/tools/execution/` | `pre_commit_detached.py`, `pre_commit_status.py` |
| `CortexResourceType.SESSION` usage | `src/cortex/` | Import paths |

### Step 2: Replace usages in both modules

Replace `_session_dir` in both files with an import from the shared module. Remove the private function definitions.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `_session_dir` references | `src/cortex/tools/execution/` | Both files |
| Import of `session_dir` | `src/cortex/tools/execution/` | Both files |

### Step 3: Update tests

Ensure existing tests still pass. Update any mocks that patch `_session_dir` to patch the new shared location.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Mock/patch of `_session_dir` | `tests/` | Pre-commit test files |

## Dependencies

- None.

## Success Criteria

- Single definition of `session_dir` in shared module.
- Both consumers import from shared module.
- No `_session_dir` definitions remain in either file.
- All existing tests pass.
- Quality gate passes.

## Testing Strategy

- Existing test coverage should transfer; update mock targets.
- Verify the shared function with a direct unit test.
- Target: 95% coverage maintained.
