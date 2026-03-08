# Make Synapse Prompts Agent-Agnostic

**Status**: PENDING
**Priority**: Medium
**Complexity**: Low
**Category**: Fix
**Component**: synapse/prompts
**Work Type**: fix
**Execution Order**: 22

## Goal

Replace Cursor-specific tool references (`ApplyPatch`, `StrReplace`, `LS`) in Synapse prompts with generic or agent-aware alternatives.

## Context

- Three prompts reference Cursor-specific tools:
  - `create-plan.md` lines 18, 112, 151: "Standard Cursor tools (`Read`, `ApplyPatch`, `Write`, `LS`, `Glob`, `Grep`)"
  - `commit.md` line 142: References `StrReplace/Write/ApplyPatch` as alternatives to `manage_file()`
  - `implement-next-roadmap-step.md` line 30: Prohibits `Write`, `StrReplace`, or `ApplyPatch` on memory bank paths
- Claude Code uses `Edit`, `Write`, `Glob`, `Grep`, `Read` — not `ApplyPatch`, `StrReplace`, or `LS`.
- Prompts should work with any agent (Cursor, Claude Code, Windsurf, etc.).

## Implementation Steps

### Step 1: Replace Cursor-specific tool names

In all three files, replace specific tool names with generic descriptions:

| Cursor Tool | Generic Replacement |
|---|---|
| `ApplyPatch` | "file edit tool" |
| `StrReplace` | "string replace tool" |
| `LS` | "directory listing tool" |

Or use a mapping note: "Standard IDE tools for file operations (Read, Edit/ApplyPatch, Write, Glob/LS, Grep)"

### Step 2: Add agent tool mapping to shared-conventions.md

**File**: `.cortex/synapse/agents/shared-conventions.md`

Add a section:

```markdown
## Agent Tool Mapping

| Operation | Generic Name | Cursor | Claude Code |
|---|---|---|---|
| Read file | Read | Read | Read |
| Edit file | Edit | ApplyPatch/StrReplace | Edit |
| Write file | Write | Write | Write |
| List/find files | Glob | LS/Glob | Glob |
| Search content | Grep | Grep | Grep |

Prompts use generic names. Agents should map to their available tools.
```

### Step 3: Update the three prompt files

**Files**: `create-plan.md`, `commit.md`, `implement-next-roadmap-step.md`

Replace all Cursor-specific tool references with generic names per the mapping.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `ApplyPatch` | `.cortex/synapse/prompts/` | Zero matches |
| `StrReplace` | `.cortex/synapse/prompts/` | Zero matches (except prohibition notes) |
| `LS` (as tool name) | `.cortex/synapse/prompts/` | Zero matches |
| `Agent Tool Mapping` | `shared-conventions.md` | Present |

## Dependencies

- None.

## Success Criteria

- No Cursor-specific tool names in prompts.
- Tool mapping table in shared-conventions.
- Prompts work with any agent.

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt changes)
- **Manual verification**: Run create-plan from Claude Code and verify it uses correct tools.
