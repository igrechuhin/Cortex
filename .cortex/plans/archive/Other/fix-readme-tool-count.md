---
title: "Fix README Tool Count Discrepancy"
component: "README"
work_type: "fix"
status: "COMPLETE"
priority: "Medium"
created: "2026-03-07"
execution_order: 19
depends_on: []
---

# Fix README Tool Count Discrepancy

**Status**: COMPLETE
**Priority**: Medium
**Complexity**: Low
**Category**: Fix / Documentation
**Component**: README
**Work Type**: fix
**Execution Order**: 19

## Goal

Correct the README's claimed tool count (27) to match the actual number of public MCP tools.

## Context

- README.md line 154 says "Cortex exposes **27 public MCP tools**".
- Code has 71 `@mcp_tool` decorators — though some may be internal/private.
- Need to determine the actual count of user-facing tools.

## Implementation Steps

### Step 1: Count actual public tools

Search for `@mcp_tool` decorators and filter for public-facing tools (exclude internal helpers if any naming convention exists).

### Step 2: Update README

Replace the hardcoded "27" with either:

- The actual count (if stable), or
- A range like "70+ MCP tools" (if count changes frequently)

### Step 3: Optionally add a CI check

Add a test or CI step that counts `@mcp_tool` decorators and compares with README claim. (Low priority — only if the count is hardcoded.)

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `27 public MCP tools` | `README.md` | Updated to correct count |

## Dependencies

- None.

## Success Criteria

- README tool count matches reality.

## Testing Strategy

- **Coverage Target**: N/A (documentation)
