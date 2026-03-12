---
title: "Consolidate Duplicate Roadmap Sync Models"
component: "validation"
work_type: "refactor"
status: "PENDING"
priority: "High"
created: "2026-03-07"
execution_order: 9
depends_on: []
---

## Consolidate Duplicate Roadmap Sync Models

**Status**: PENDING
**Priority**: High
**Complexity**: Medium
**Category**: Refactoring
**Component**: validation
**Work Type**: refactor
**Execution Order**: 9

## Goal

Remove the legacy duplicate model set in `roadmap_models.py` and consolidate to the canonical models in `roadmap_sync.py`.

## Context

- `src/cortex/validation/roadmap_models.py` (56 lines) defines `TodoItemModel`, `RoadmapReferenceModel`, `SyncValidationResultModel` — its own docstring says "These models were originally defined in `validation.models`."
- `src/cortex/validation/roadmap_sync.py` defines `TodoItem`, `RoadmapReference`, `SyncValidationResult` with additional fields.
- Both model sets are Pydantic v2 with `ConfigDict(extra="forbid")`.
- The `roadmap_models.py` versions appear to be legacy. Need to verify which are actually imported/used before removing.

## Implementation Steps

### Step 1: Find all imports of both model sets

Search for:

- `from cortex.validation.roadmap_models import` — list all consumers
- `from cortex.validation.roadmap_sync import TodoItem` (and other model names)
- Any re-exports from `__init__.py`

### Step 2: Compare field sets

| Field | `roadmap_models.py` | `roadmap_sync.py` | Action |
|---|---|---|---|
| TodoItem.file_path | `str` | Check | Keep canonical |
| TodoItem.line | `int` (ge=1) | Check | Keep canonical |
| TodoItem.snippet | `str` | Check | Keep canonical |
| TodoItem.category | `str` | Check | Keep canonical |
| Additional fields | — | Identify | Keep in canonical |

### Step 3: Migrate consumers to canonical models

For each consumer of `roadmap_models.py`:

- Update import to use `roadmap_sync.py` models
- Verify field compatibility (the canonical models should be supersets)
- Run tests to confirm no breakage

### Step 4: Delete roadmap_models.py

Remove the file. Update `__init__.py` if it re-exports these models.

### Step 5: Run full test suite

Ensure no import errors or field mismatches.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `roadmap_models` | Full repo | Zero imports (file deleted) |
| `TodoItemModel` | Full repo | Zero references |
| `TodoItem` | `src/cortex/validation/` | Only in `roadmap_sync.py` |

## Dependencies

- None.

## Success Criteria

- `roadmap_models.py` is deleted.
- All consumers use the canonical models from `roadmap_sync.py`.
- All tests pass.

## Testing Strategy

- **Coverage Target**: 95% for modified files
- **Unit tests**: Existing tests should pass unchanged (models are compatible)
- **Integration**: Run roadmap sync validation end-to-end
