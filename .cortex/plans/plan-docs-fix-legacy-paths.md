# Fix Legacy .memory-bank/ Path References in Documentation

**Status**: PENDING
**Priority**: CRITICAL
**Created**: 2026-02-28
**Type**: Fix
**Effort**: Large (1-2 hours)

## Goal

Replace all legacy `.memory-bank/` path references in documentation with the current `.cortex/` layout, and update the architecture.md Storage Layer diagram to reflect the actual current storage structure.

## Context

The project migrated from `.memory-bank/` to `.cortex/memory-bank/` and from `.memory-bank-index` to `.cortex/index.json`, but ~50 references across 12+ docs files still describe the legacy layout as current. This is actively misleading for anyone reading the docs.

**Current layout** (as described in README.md):

- `.cortex/memory-bank/` — core memory bank files
- `.cortex/index.json` — metadata index
- `.cortex/history/` — version snapshots
- `.cortex/.cache/` — cache files (learning data, access log, usage)
- `.cortex/plans/` — development plans
- `.cortex/config/` — configuration

**Legacy layout** (still in docs):

- `.memory-bank/knowledge/` — files
- `.memory-bank-index` — metadata JSON
- `.memory-bank-access-log.json` — usage patterns
- `.memory-bank-learning.json` — learning data
- `.memory-bank-approvals.json` — approval records
- `.memory-bank-refactoring-history.json` — execution history
- `.memory-bank-rollbacks.json` — rollback history

## Approach

Systematic search-and-replace across all affected docs, then rewrite the architecture.md Storage Layer section and ASCII diagram.

## Implementation Steps

1. **Map legacy → current paths**:
   - `.memory-bank/knowledge/` → `.cortex/memory-bank/`
   - `.memory-bank/rules/` → `.cortex/rules/` or `.cortex/synapse/rules/`
   - `.memory-bank/plans/` → `.cortex/plans/`
   - `.memory-bank-index` → `.cortex/index.json`
   - `.memory-bank-access-log.json` → `.cortex/.cache/usage/` (or removed)
   - `.memory-bank-learning.json` → `.cortex/.cache/learning.json`
   - `.memory-bank-approvals.json` → `.cortex/.cache/` (verify actual location)
   - `.memory-bank-refactoring-history.json` → `.cortex/.cache/` (verify actual location)
   - `.memory-bank-rollbacks.json` → `.cortex/.cache/` (verify actual location)
2. **Verify actual current paths** in source code before updating docs:
   - Check `src/cortex/core/path_resolver.py` and `src/cortex/structure/structure_config.py` for canonical paths
   - Check `src/cortex/core/metadata_index.py` for index file path
   - Check `src/cortex/refactoring/rollback_manager.py` for rollback file path
3. **Update docs/architecture.md**:
   - Rewrite ASCII diagram (lines 17-63) to show `.cortex/` layout
   - Rewrite "Layer 5: Storage" section (lines 223-239) with current paths
   - Update "Not Git-Tracked" subsection with current cache paths
4. **Update docs/getting-started.md**:
   - Lines 144-145: `.memory-bank/` → `.cortex/memory-bank/`
   - Lines 163-165: `.memory-bank/knowledge/` → `.cortex/memory-bank/`, etc.
   - Line 229: `.memory-bank/knowledge/` → `.cortex/memory-bank/`
   - Line 145: `.memory-bank-index` → `.cortex/index.json`
5. **Update docs/index.md**:
   - Line 80: `.memory-bank/` → `.cortex/memory-bank/`
6. **Update docs/guides/failure-modes.md**:
   - Lines 35, 53, 665, 688, 704: `.memory-bank-index` → `.cortex/index.json`
7. **Update docs/guides/troubleshooting.md**:
   - Lines 1186, 1402-1408: All legacy metadata file references
8. **Update docs/guides/configuration.md**:
   - Lines 340, 484-489: All legacy metadata file references
9. **Update docs/guides/error-recovery.md**:
   - Lines 223, 234, 509: `.memory-bank-index` → `.cortex/index.json`
10. **Update docs/api/managers.md**:
    - Lines 190, 209: `.memory-bank-index` → `.cortex/index.json`
11. **Update docs/api/modules.md**:
    - Line 95: `.memory-bank-index` → `.cortex/index.json`
12. **Full sweep**: `grep -rn "\.memory-bank" docs/` — fix any remaining references
13. **Note**: ADR files (`docs/adr/`) describe historical decisions and should be left as-is (they document what was decided at the time)

## Dependencies

None.

## Success Criteria

- `grep -rn "\.memory-bank/" docs/ | grep -v adr/ | grep -v "legacy\|migrat\|old format"` returns empty (only references in migration/legacy context)
- `grep -rn "\.memory-bank-index\|memory-bank-access-log\|memory-bank-learning\|memory-bank-approvals\|memory-bank-refactoring\|memory-bank-rollbacks" docs/ | grep -v adr/` returns empty
- docs/architecture.md diagram shows `.cortex/` layout
- All paths in docs match actual source code paths

## Testing Strategy

- **Coverage Target**: N/A (docs-only change)
- **Verification**: Grep sweeps for legacy paths; visual review of architecture diagram
- **Regression**: No code changes

## Risks & Mitigation

- **Risk**: Some paths may have changed in ways not documented → **Mitigation**: Verify each path against source code in step 2
- **Risk**: Missing some references → **Mitigation**: Full `grep -rn "\.memory-bank"` sweep in step 12

## Timeline

1-2 sessions (1-2 hours). Can be split: architecture.md first, then guides.
