---
title: "Add Structured Quality Configuration"
component: "cortex/config"
work_type: feature
status: DONE
priority: High
created: 2026-03-07
execution_order: 7
depends_on: []
---

## Add Structured Quality Configuration

**Status**: PENDING
**Priority**: High
**Complexity**: Medium
**Category**: Feature / Infrastructure
**Component**: cortex/config
**Work Type**: feature
**Execution Order**: 7

## Goal

Replace fragile markdown-parsed quality thresholds with a structured `.cortex/config/quality.json` file, providing a single source of truth for coverage thresholds, file size limits, and other quality parameters.

## Context

- Coverage threshold is currently parsed from `progress.md` or `techContext.md` by searching for `coverage_threshold: <value>` in markdown (commit.md line 130).
- Variations like `Coverage Threshold: 85%`, `coverage_threshold = 0.85`, or table-formatted values would all fail to parse.
- Multiple consumers need these values: commit pipeline, review pipeline, quality checks.
- External review rated this as **High** priority.

## Implementation Steps

### Step 1: Create quality.json schema and file

**File**: `.cortex/config/quality.json` (new)

```json
{
  "$schema": "cortex-quality-config-v1",
  "coverage_threshold": 90,
  "max_file_lines": 400,
  "max_function_lines": 30,
  "test_timeout_seconds": 120,
  "todo_patterns": ["TODO", "FIXME", "HACK", "XXX"],
  "exclude_from_todo_scan": ["tests/", "examples/", "samples/", "demos/"],
  "markdown_line_length": 120
}
```

### Step 2: Create Pydantic model for the config

**File**: `src/cortex/config/quality_config.py` (new)

```python
class QualityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage_threshold: int = Field(default=90, ge=0, le=100)
    max_file_lines: int = Field(default=400, ge=100)
    max_function_lines: int = Field(default=30, ge=10)
    test_timeout_seconds: int = Field(default=120, ge=10)
    todo_patterns: list[str] = Field(default=["TODO", "FIXME", "HACK", "XXX"])
    exclude_from_todo_scan: list[str] = Field(default=["tests/", "examples/"])
    markdown_line_length: int = Field(default=120, ge=80)
```

Add a loader function: `load_quality_config(project_root: Path) -> QualityConfig` that reads `.cortex/config/quality.json` with fallback defaults.

### Step 3: Update commit.md to reference quality.json

**File**: `.cortex/synapse/prompts/commit.md`

Replace the coverage threshold override section (line ~130) with: "Read coverage threshold from `.cortex/config/quality.json` via `load_quality_config()`. Fallback: 90% if config file missing."

### Step 4: Update roadmap_sync.py to use config for TODO patterns

**File**: `src/cortex/validation/roadmap_sync.py`

Import and use `QualityConfig.todo_patterns` and `QualityConfig.exclude_from_todo_scan` instead of hardcoded patterns. (Coordinate with `fix-todo-scanner-exclusion-patterns` plan.)

### Step 5: Add unit tests

**File**: `tests/unit/test_quality_config.py` (new)

Test cases: default values, custom overrides, missing file fallback, invalid values rejected, extra fields rejected.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `quality.json` | `.cortex/config/` | File exists with valid schema |
| `QualityConfig` | `src/cortex/config/` | Pydantic model with validation |
| `load_quality_config` | `src/cortex/` | Loader function used by consumers |

## Dependencies

- Coordinates with `fix-todo-scanner-exclusion-patterns` (shares exclude patterns).

## Success Criteria

- `.cortex/config/quality.json` exists and is validated by Pydantic model.
- Commit pipeline reads thresholds from config, not markdown.
- TODO scanner uses config for patterns and exclusions.
- All tests pass.

## Testing Strategy

- **Coverage Target**: 95%
- **Unit tests**: Model validation, loader, defaults, error cases
- **Integration**: Commit pipeline uses config values correctly
