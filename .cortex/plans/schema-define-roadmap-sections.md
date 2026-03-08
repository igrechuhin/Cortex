# Schema-Define Roadmap Section Names

**Status**: PENDING
**Priority**: Medium
**Complexity**: Low
**Category**: Fix
**Component**: tools/plans
**Work Type**: fix
**Execution Order**: 18

## Goal

Replace hardcoded roadmap section name strings with a Pydantic model or constants module, and have the MCP tool auto-create missing sections instead of failing silently.

## Context

- `src/cortex/tools/plans/register_helpers.py` lines 22-27 hardcode section names:

  ```python
  header_to_section = {
      "Blockers (ASAP Priority)": "blockers",
      "Active Work (in progress)": "active_work",
      "Future Enhancements": "future",
      "Pending plans (from .cortex/plans)": "pending",
  }
  ```

- If `roadmap.md` header text is renamed (e.g., "Blockers (ASAP)" instead of "Blockers (ASAP Priority)"), the mapping breaks silently.
- No auto-creation of missing sections — if a section header is missing from roadmap.md, plan registration fails.

## Implementation Steps

### Step 1: Create a constants/model for section names

**File**: `src/cortex/validation/roadmap_constants.py` (new, or add to existing models)

```python
from enum import StrEnum

class RoadmapSection(StrEnum):
    BLOCKERS = "Blockers (ASAP Priority)"
    ACTIVE_WORK = "Active Work (in progress)"
    FUTURE = "Future Enhancements"
    PENDING = "Pending plans (from .cortex/plans)"

SECTION_TO_KEY: dict[str, str] = {
    RoadmapSection.BLOCKERS: "blockers",
    RoadmapSection.ACTIVE_WORK: "active_work",
    RoadmapSection.FUTURE: "future",
    RoadmapSection.PENDING: "pending",
}
```

### Step 2: Update register_helpers.py to use constants

**File**: `src/cortex/tools/plans/register_helpers.py`

Replace `header_to_section` dict with import from `roadmap_constants.py`.

### Step 3: Add auto-creation of missing sections

In the registration logic, if the target section header is not found in roadmap.md:

1. Log a warning: "Section '{header}' not found in roadmap.md, creating it."
2. Append the section header at the appropriate position.
3. Proceed with registration.

### Step 4: Add tests

**File**: `tests/unit/test_roadmap_constants.py` (new)

Test cases:

- All enum values match expected header strings
- `SECTION_TO_KEY` covers all enum values
- Registration succeeds when section exists
- Registration auto-creates missing section

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `RoadmapSection` | `src/cortex/` | Enum defined and imported |
| `header_to_section` | `register_helpers.py` | Uses constants, not literal strings |

## Dependencies

- None.

## Success Criteria

- Section names defined once in a constants module.
- `register_helpers.py` uses the constants.
- Missing sections are auto-created with a warning.
- All tests pass.

## Testing Strategy

- **Coverage Target**: 95% for modified code
- **Unit tests**: 4+ test cases
