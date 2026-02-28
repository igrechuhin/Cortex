# Deduplicate Token Budget Table

**Status**: PENDING
**Priority**: MEDIUM
**Created**: 2026-02-28
**Type**: Cleanup (DRY)
**Effort**: Small (10 min)

## Goal

Remove the duplicated context budget defaults table that appears in both `CLAUDE.md` and `AGENTS.md`.

## Context

The identical "Context budget defaults (task-type)" table appears in:

- `CLAUDE.md` lines 29-38
- `AGENTS.md` lines 57-66

This DRY violation requires double updates when budget defaults change.

## Approach

Keep the table in `AGENTS.md` (full workflow context) and replace with a cross-reference in `CLAUDE.md`.

## Implementation Steps

1. **In `CLAUDE.md`**: Replace the table (lines 29-38) with:

   ```markdown
   **Context budget defaults**: See [AGENTS.md](AGENTS.md#workflow) for the token budget table by task type.
   ```

2. **Verify**: `AGENTS.md` still has the complete table
3. **Check no other files** duplicate this table: `grep -rn "implement/add, update/modify" .`

## Dependencies

None.

## Success Criteria

- Table exists in exactly one location (`AGENTS.md`)
- Cross-reference in `CLAUDE.md` is valid
- No other duplicates exist

## Testing Strategy

- **Coverage Target**: N/A (docs-only change)
- **Verification**: Grep confirms single instance
- **Regression**: No code changes

## Risks & Mitigation

- **Risk**: Agents that read only CLAUDE.md miss budget info → **Mitigation**: Cross-reference is explicit

## Timeline

Single session (10 min).
