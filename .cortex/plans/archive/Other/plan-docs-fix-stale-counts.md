# Fix Stale Tool/Test/Module Counts in Documentation

**Status**: PENDING
**Priority**: HIGH
**Created**: 2026-02-28
**Type**: Fix
**Effort**: Medium (30 min)

## Goal

Update all documentation files that reference outdated tool counts ("100+ tools"), test counts ("3700+ tests"), and module counts ("41+ modules") to reflect the current state after Phase 50 tool consolidation.

## Context

After Phase 50 tool consolidation, the actual tool count is 71 (per `src/cortex/tools/__init__.py` line 33: "Total: 71 tools + 7 prompts"). README.md says "60+", docs say "100+". The test suite has grown to ~4850 tests. Multiple docs still reference old numbers:

- `docs/architecture.md` ~line 96: "100+ tools"
- `docs/api/tools.md` ~line 95: "100+ tools"
- `docs/testing-speed-optimization.md` ~line 3: "3700+ tests"
- `AGENTS.md` line 165: hardcoded "4799 passed"
- `docs/architecture.md` ~line 109: "41+ modules"

## Approach

Count actual values from source, then update all docs in one pass.

## Implementation Steps

1. **Count actual MCP tools**: Inspect `src/cortex/server.py` or tool registration to get exact count
2. **Count actual tests**: `uv run pytest tests/ --collect-only -q | tail -1`
3. **Count actual modules**: `find src/cortex -maxdepth 1 -type d | wc -l`
4. **Search all docs for stale references**: `grep -rn "100+" docs/` and `grep -rn "3700" docs/` and `grep -rn "4799" .`
5. **Update each file**:
   - `docs/architecture.md` — tool count, module count
   - `docs/api/tools.md` — tool count, pruned tools table
   - `docs/testing-speed-optimization.md` — test count
   - `AGENTS.md` line 165 — replace hardcoded count with "as of 2026-02-28" or remove
   - Any other files found in step 4
6. **Verify consistency**: Search again to confirm no stale counts remain

## Dependencies

None.

## Success Criteria

- All docs reference consistent, correct counts
- No hardcoded test counts without dates
- `grep -rn "100+ tools\|100+ MCP" docs/` returns empty

## Testing Strategy

- **Coverage Target**: N/A (docs-only change)
- **Verification**: Grep searches confirm no stale counts
- **Regression**: No code changes

## Risks & Mitigation

- **Risk**: Counts become stale again → **Mitigation**: Use approximate language ("70+ tools") or reference `__init__.py` as source of truth

## Timeline

Single session (30 min).
