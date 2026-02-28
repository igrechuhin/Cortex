# Consolidate Duplicate Protocol Documentation

**Status**: PENDING
**Priority**: MEDIUM
**Created**: 2026-02-28
**Type**: Cleanup (DRY)
**Effort**: Small (10 min)

## Goal

Eliminate DRY violation where protocol documentation exists in two places with overlapping content.

## Context

Protocol documentation exists in two files:

- `docs/architecture/protocols.md` — architecture perspective
- `docs/api/protocols.md` — API reference perspective

Both contain the same protocol definitions, requiring double updates on changes.

## Approach

Keep `docs/api/protocols.md` as the canonical source (API reference is authoritative). Replace `docs/architecture/protocols.md` with a cross-reference.

## Implementation Steps

1. **Compare both files**: Diff content to confirm overlap
2. **Keep `docs/api/protocols.md`** as canonical source
3. **Replace `docs/architecture/protocols.md`** with:

   ```markdown
   # Protocols

   See [API Protocol Reference](../api/protocols.md) for the complete protocol documentation.
   ```

4. **Update links**: Search for any references to architecture/protocols.md and update if needed
5. **Verify**: All links resolve correctly

## Dependencies

None.

## Success Criteria

- Only one authoritative protocol document exists
- Cross-reference from architecture/ to api/ works
- No broken links

## Testing Strategy

- **Coverage Target**: N/A (docs-only change)
- **Verification**: Link validation via grep
- **Regression**: No code changes

## Risks & Mitigation

- **Risk**: Some unique content in architecture version → **Mitigation**: Compare files first, merge unique content into API version

## Timeline

Single session (10 min).
