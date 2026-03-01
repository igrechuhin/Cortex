# Remove Empty Archive Files and Stale History

**Status**: PENDING
**Priority**: LOW
**Created**: 2026-02-28
**Type**: Cleanup
**Effort**: Tiny (5 min)

## Goal

Delete 3 empty (0-byte) files in `.cortex/` that are placeholder artifacts with no content.

## Context

3 empty files were found during project review:

1. `.cortex/plans/archive/Investigations/2026-02-04/phase-investigate-capture_session_script-failure-20260204-080339.md`
2. `.cortex/plans/archive/Phase63/phase-63-harden-create-plan-roadmap-writes.md`
3. `.cortex/history/test_verification_v4.md`

These are empty placeholders from completed investigations/phases.

## Approach

Delete files, clean up empty parent directories.

## Implementation Steps

1. **Delete all 3 empty files**
2. **Check parent directories**: If empty after deletion, remove them too
3. **Verify**: `find .cortex -empty -name "*.md"` returns empty
4. **Check no references** point to these files: `grep -rn "capture_session_script\|phase-63-harden\|test_verification_v4" .cortex/`

## Dependencies

None.

## Success Criteria

- No empty `.md` files exist in `.cortex/`
- No broken references to deleted files

## Testing Strategy

- **Coverage Target**: N/A (cleanup-only change)
- **Verification**: `find .cortex -empty -name "*.md"` returns empty
- **Regression**: No code changes

## Risks & Mitigation

None — files are 0 bytes with no content.

## Timeline

Single session (5 min).
