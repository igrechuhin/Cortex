# Rename roadmap-fix-temp.md to Permanent Name

**Status**: PENDING
**Priority**: LOW
**Created**: 2026-02-28
**Type**: Cleanup
**Effort**: Tiny (5 min)

## Goal

Rename `docs/design/roadmap-fix-temp.md` to `docs/design/roadmap.md`, removing the misleading "fix-temp" suffix.

## Context

`docs/design/roadmap-fix-temp.md` is the active roadmap design document but its name suggests it's temporary. The "fix-temp" suffix is misleading and should be removed.

## Approach

Rename file, update references.

## Implementation Steps

1. **Rename**: `docs/design/roadmap-fix-temp.md` → `docs/design/roadmap.md`
2. **Search for references**: `grep -rn "roadmap-fix-temp" .`
3. **Update all references** to point to new name
4. **Verify links** work

## Dependencies

None.

## Success Criteria

- File exists at `docs/design/roadmap.md`
- No references to `roadmap-fix-temp` remain

## Testing Strategy

- **Coverage Target**: N/A (docs-only change)
- **Verification**: Grep for old name returns empty
- **Regression**: No code changes

## Risks & Mitigation

None.

## Timeline

Single session (5 min).
