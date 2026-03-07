# Phase 87: Stale `exec()` Comment and Dead Reference Cleanup

**Status**: PENDING
**Priority**: Low
**Complexity**: Low
**Category**: Cleanup

## Goal

Remove stale comments referencing removed code patterns (e.g., `exec()`) and audit for other dead references across the codebase.

## Context

- `src/cortex/tools/synapse/prompts.py:29` contains: `# Explicitly reference mcp to satisfy type checker (used in exec() string)` — but no `exec()` call exists in `src/` anymore. The exec() was removed in a security cleanup but the comment was left behind.
- Chat sessions discussed `exec()` removal as a security fix but follow-through on comment cleanup was incomplete.

## Implementation Steps

### Step 1: Fix the stale exec() comment

- Read `src/cortex/tools/synapse/prompts.py` around line 29.
- Determine if the `mcp` reference is still needed for the type checker.
- If yes, update the comment to reflect the actual reason.
- If no, remove both the comment and the unused reference.

### Step 2: Audit for other dead comments

- Search for comments mentioning removed patterns: `exec(`, `eval(`, `TYPE_CHECKING`, `TypedDict`.
- Search for TODO/FIXME/HACK comments that reference completed phases or resolved issues.
- Remove or update stale comments.

### Step 3: Verify

- Run type checker to ensure no removed references are still needed.
- Run tests.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `exec()` in comments | `src/` | Zero references to removed exec() usage |
| `TypedDict` in comments | `src/` | Zero stale references |

## Dependencies

- None.

## Success Criteria

- No stale comments referencing removed code patterns.
- Type checker passes after any reference removals.

## Testing Strategy

- **Coverage Target**: N/A (comment cleanup only).
- **Verification**: `pyright src/` passes with 0 errors.

## Timeline

- Estimated: 30 minutes.
