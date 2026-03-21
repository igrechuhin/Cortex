---
title: "Sanitize pipeline/phase path parameters in pipeline_handoff"
component: security
work_type: fix
status: PENDING
priority: high
created: 2026-03-21
depends_on: []
---

## Goal

Add strict validation for `pipeline` and `phase` string parameters in `pipeline_handoff` tool to prevent path traversal, ensuring filesystem writes stay within the intended `.cortex/.session/{session_id}/` subtree.

## Context

- Flagged in code review `2026-03-20T15-55` as High severity (finding #1).
- `src/cortex/tools/session/pipeline_handoff.py:67-80`: `_pipeline_dir()` uses `base / session_id / pipeline` and `_task_path()` uses `f"{phase}-task.json"` — both directly from user-supplied strings without sanitization.
- While these parameters currently come from the commit prompt (not external users), defense-in-depth requires validation at the boundary.
- The fix is small: validate against an allowlist of known pipeline/phase names.

## Implementation Steps

### Step 1: Add validation constants

- **File**: `src/cortex/tools/session/pipeline_handoff.py`
- Add: `_VALID_PIPELINES: frozenset[str] = frozenset({"commit", "implement", "fix", "review"})`
- Add: `_VALID_PHASES: frozenset[str] = frozenset({"preflight", "checks", "docs", "validate", "final-gate", "selection", "implementation"})`
- Both sets derived from actual usage in Synapse prompts

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `_VALID_PIPELINES` constant | `pipeline_handoff.py` | Top of file |
| Pipeline names in Synapse prompts | `.cortex/synapse/prompts/*.md` | commit.md, implement.md |

### Step 2: Add validation to path-building functions

- **File**: `src/cortex/tools/session/pipeline_handoff.py`
- In `_pipeline_dir()`: validate `pipeline in _VALID_PIPELINES`, raise `ValueError` if not
- In `_task_path()` and `_result_path()`: validate `phase in _VALID_PHASES`, raise `ValueError` if not
- Additionally, reject any string containing `/`, `\`, `..`, or null bytes as a belt-and-suspenders check

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Validation in `_pipeline_dir` | `pipeline_handoff.py` | Lines 67-80 |
| Path separator rejection | Same | Same |

### Step 3: Add tests for path validation

- **File**: `tests/unit/test_pipeline_handoff_path_safety.py` (new)
- Test valid pipeline/phase names pass
- Test invalid names (path traversal, unknown names) raise ValueError
- Test that the tool returns an error response (not a crash) when validation fails

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Path safety tests | `tests/unit/test_pipeline_handoff_path_safety.py` | New test file |
| Edge cases: `../`, null bytes | Same | Same |

## Dependencies

None.

## Success Criteria

- `_pipeline_dir` and `_task_path` reject unknown or malicious inputs
- All existing pipeline_handoff callers continue to work (valid names unchanged)
- Path traversal attempts raise ValueError with clear message
- Quality gate passes

## Testing Strategy

- Unit tests for validation logic: valid names, invalid names, path traversal attempts
- Existing integration tests for commit/implement pipelines continue to pass
- 95%+ coverage on the new validation code
