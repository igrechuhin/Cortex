---
title: "Tighten tool-count guardrail from MAX=16 to MAX=12"
component: governance
work_type: fix
status: DONE
priority: Medium
created: 2026-03-21
depends_on: []
---

## Goal

Reduce `MAX_REGISTERED_TOOLS` from 16 to 12 (20% buffer above the 10-tool target) to prevent silent surface-area regression, and require an explicit ADR/plan to raise it.

## Context

- `src/cortex/tools/structure/categories.py:31`: `MAX_REGISTERED_TOOLS = 16`
- `src/cortex/tools/structure/categories.py:34`: `TARGET_REGISTERED_TOOLS = 10`
- Currently at exactly 10 tools — the 60% headroom (16 vs 10) allows 6 tools to be added without any governance test failing.
- The consolidation from 70+ to 10 tools was a deliberate architectural decision. A tight guardrail protects this investment.
- Governance test: `tests/tools/test_tool_categories_governance.py` enforces the max.

## Implementation Steps

### Step 1: Reduce MAX_REGISTERED_TOOLS

- **File**: `src/cortex/tools/structure/categories.py:31`
- **Before**: `MAX_REGISTERED_TOOLS = 16`
- **After**: `MAX_REGISTERED_TOOLS = 12`
- Update the comment to state: "Hard cap. To raise, create a plan documenting why the new tool cannot be consolidated into an existing one."

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `MAX_REGISTERED_TOOLS` value | `src/cortex/tools/structure/categories.py` | categories.py |
| Governance test still passes | `tests/tools/test_tool_categories_governance.py` | Test file |

### Step 2: Add escalation documentation

- **File**: `docs/api/tools.md` (add section "Adding new tools")
- Document the process: (1) check if functionality fits an existing tool, (2) if not, create a plan justifying the new tool, (3) get approval, (4) raise `MAX_REGISTERED_TOOLS` in the same PR
- Reference `TARGET_REGISTERED_TOOLS = 10` as the consolidation goal

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| "Adding new tools" section | `docs/api/tools.md` | tools.md |

## Dependencies

None.

## Success Criteria

- `MAX_REGISTERED_TOOLS` is 12
- Governance test passes with current 10 tools
- Documented escalation process for adding tools beyond 12

## Testing Strategy

- `test_tool_categories_governance.py` continues to pass (10 < 12)
- Add a test that verifies `MAX_REGISTERED_TOOLS <= 12` as a constant assertion
- 95%+ test coverage maintained
