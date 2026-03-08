# Fix Sensitive Data Leakage in Roadmap Logging

**Status**: PENDING
**Priority**: High
**Complexity**: Low
**Category**: Fix / Security
**Component**: validation/roadmap_sync
**Work Type**: fix
**Execution Order**: 10

## Goal

Reduce log verbosity in roadmap sync ghost-section detection to prevent leaking sensitive planning content, and downgrade severity from error to warning.

## Context

- When ghost sections are detected, `roadmap_sync.py` logs full content previews (first 1000 + last 500 characters) at error level with "CRITICAL" wording.
- Roadmap content may contain sensitive planning information, feature names, or internal priorities.
- Logging at error level with "CRITICAL" prefix triggers alert fatigue and misclassifies the severity.

## Implementation Steps

### Step 1: Find the ghost section logging code

**File**: `src/cortex/validation/roadmap_sync.py`

Search for `CRITICAL` or `ghost` in logging calls. Identify the exact lines that log content previews.

### Step 2: Replace content logging with metadata

Replace:

```python
logger.error(f"CRITICAL: Ghost section detected. Content preview: {content[:1000]}...{content[-500:]}")
```

With:

```python
logger.warning(
    "Ghost section detected in roadmap",
    extra={"file_path": str(path), "file_size": len(content), "section_names": section_names}
)
```

### Step 3: Verify no other content-logging patterns exist

Search for `content[:` or `content[` in logging calls across `roadmap_sync.py` to catch other instances.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `content[:1000]` or `content[-500:]` | `roadmap_sync.py` | Zero matches |
| `CRITICAL.*ghost` or `CRITICAL.*Ghost` | `roadmap_sync.py` | Zero matches |
| `logger.warning.*ghost` or `Ghost section` | `roadmap_sync.py` | Present (downgraded) |

## Dependencies

- None.

## Success Criteria

- Ghost section logs contain only metadata (path, size, section names).
- Log level is `warning`, not `error`.
- No content previews in any log output.

## Testing Strategy

- **Coverage Target**: 95% for modified code
- **Unit test**: Trigger ghost section detection and assert log output contains no content preview.
