---
title: "Targeted exception narrowing in validation and config paths"
component: core
work_type: fix
status: PENDING
priority: Medium
created: 2026-03-21
depends_on: []
---

## Goal

Replace broad `except Exception` with specific exception types in the 5 highest-impact locations identified across 14 code reviews, preventing swallowed bugs while preserving defensive boundaries.

## Context

- "Narrow `except Exception`" has been flagged in 12 of 14 code reviews without resolution, because suggestions lacked concrete file:line targets.
- This plan provides the exact locations, before/after code, and scope for each change.
- Project rule: prefer specific exceptions; retain `Exception` only at deliberate top-level boundaries with logging.
- Not all `except Exception` is wrong — integration boundaries (MCP tool handlers, migration runners) legitimately need broad catches. This plan targets only the cases where specific exceptions are known and broad catches hide bugs.

## Implementation Steps

### Step 1: validation_config.py — config file parsing

- **File**: `src/cortex/validation/validation_config.py:92`
- **Before**: `except Exception:` on `model_validate` — silently returns defaults
- **After**: `except (OSError, json.JSONDecodeError) as e:` for file I/O, then separate `except ValidationError as e:` with logging, then return defaults
- **Rationale**: `model_validate` can raise `ValidationError` (Pydantic) or `OSError`/`JSONDecodeError` (file reading). Programming errors (TypeError, AttributeError) should propagate.

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `except Exception` in validation_config | `src/cortex/validation/validation_config.py` | Lines 85-100 |
| `ValidationError` import added | Same file | Top imports |

### Step 2: validation_config.py — second broad catch

- **File**: `src/cortex/validation/validation_config.py:63`
- Same pattern as Step 1 — narrow to `(OSError, json.JSONDecodeError)`

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `except Exception` at line ~63 | `src/cortex/validation/validation_config.py` | Lines 55-70 |

### Step 3: validation_config.py — third broad catch

- **File**: `src/cortex/validation/validation_config.py:190`
- Narrow to expected types for the operation at that location

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `except Exception` at line ~190 | `src/cortex/validation/validation_config.py` | Lines 185-200 |

### Step 4: completion_io.py — plan file I/O

- **File**: `src/cortex/tools/plans/completion_io.py` (multiple handlers)
- Narrow file-reading catches to `(OSError, json.JSONDecodeError, UnicodeDecodeError)`
- Keep `Exception` only at the outermost MCP tool boundary if present

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `except Exception` in completion_io | `src/cortex/tools/plans/completion_io.py` | All exception handlers |

### Step 5: container.py — post-init setup

- **File**: `src/cortex/core/container.py:251-271`
- `_post_init_setup()` catches `except Exception as e:` for metadata index load and rules init
- Narrow to `(OSError, json.JSONDecodeError, ValidationError)` and add `exc_info=True` to logging

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `except Exception` in _post_init_setup | `src/cortex/core/container.py` | Lines 245-275 |
| `exc_info=True` in logging | Same | Same |

## Dependencies

None.

## Success Criteria

- Zero `except Exception` in the 5 targeted locations
- All narrowed catches use specific exception types appropriate to the operation
- All catches include logging with `exc_info=True` for unexpected failures
- Quality gate passes (types, lint, tests)
- No behavior change for expected failure paths (still returns defaults/logs gracefully)

## Testing Strategy

- Existing tests for validation_config, completion_io, container continue to pass
- Add targeted tests that verify specific exceptions are caught and logged appropriately
- Add tests that verify programming errors (e.g. TypeError) now propagate instead of being swallowed
- 95%+ coverage maintained
