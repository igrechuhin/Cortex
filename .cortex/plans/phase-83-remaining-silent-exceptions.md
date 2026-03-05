# Phase 83: Remaining Silent Exception Handlers

**Status**: PENDING
**Priority**: Medium
**Complexity**: Low
**Category**: Fix / Quality

## Goal

Eliminate the 7 remaining `except Exception: pass/continue` blocks in `src/` by adding proper logging and narrowing exception types.

## Context

- Phase 77 fixed 11 silent exception blocks, but 7 more remain.
- Silent exceptions hide bugs and make debugging extremely difficult.
- Chat sessions showed recurring issues traced back to silently swallowed errors.

## Remaining Instances

| # | File | Line | Pattern |
|---|------|------|---------|
| 1 | `validation/infrastructure_validator.py` | 286-287 | `except Exception: pass` |
| 2 | `validation/infrastructure_validator.py` | 347-348 | `except Exception: pass` |
| 3 | `refactoring/refactoring_executor_history.py` | 51-52 | `except Exception: continue` |
| 4 | `core/mcp_stability_progress.py` | 45-46 | `except Exception: pass` |
| 5 | `tools/execution/workflow_operations.py` | 41-42 | `except Exception: continue` |
| 6 | `tools/evaluation/_optimization.py` | 81-82 | `except Exception: continue` |
| 7 | `tools/plans/crud_helpers.py` | 160-161 | `except Exception: pass` |

## Implementation Steps

### Step 1: Analyze each handler

- For each of the 7 locations, read the surrounding code to understand what operation is being protected.
- Determine the specific exceptions that could be raised.

### Step 2: Fix each handler

For each location:

1. Narrow `except Exception` to the specific exception type(s) (`OSError`, `ValueError`, `json.JSONDecodeError`, `ValidationError`, etc.).
2. Add `logger.debug(...)` or `logger.warning(...)` with context about what failed.
3. Ensure the module has a logger defined (`logger = logging.getLogger(__name__)`).

### Step 3: Verify

- Run type checker and quality gate.
- Run full test suite.
- Grep for remaining `except Exception.*pass` and `except Exception.*continue` patterns.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `except Exception:` followed by `pass` | `src/` | Zero matches |
| `except Exception:` followed by `continue` | `src/` | Zero matches |

## Dependencies

- None.

## Success Criteria

- Zero `except Exception: pass/continue` patterns in `src/`.
- All handlers have appropriate logging.
- All handlers use narrowed exception types.
- All tests pass.

## Testing Strategy

- **Coverage Target**: 95%+ for modified functions.
- **Unit Tests**: Existing tests should continue to pass.
- **Edge Cases**: Verify that the narrower exceptions still catch the intended failures.

## Risks & Mitigation

- **Risk**: Narrowed exceptions miss an edge case. **Mitigation**: Use `logger.exception()` for unexpected failures.

## Timeline

- Estimated: 1–2 hours.
