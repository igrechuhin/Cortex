# Fix Tool Files Exceeding 400-Line Limit

**Status**: PENDING
**Priority**: HIGH
**Created**: 2026-02-28
**Type**: Refactoring
**Effort**: Large (multi-session)

## Goal

Split all 26 files in `src/cortex/tools/` that exceed the project's 400-line limit into cohesive submodules.

## Context

The project rule mandates files <= 400 lines (production code), but 26 files in `src/cortex/tools/` violate this. Top offenders:

| File | Lines |
|------|-------|
| `compaction_operations.py` | 670 |
| `validation_operations.py` | 620 |
| `analysis_operations.py` | 598 |
| `roadmap_corruption.py` | 586 |
| `phase5_production_monitoring_helpers.py` | 580 |
| `task_locking.py` | 572 |
| `refactoring_operations.py` | 565 |
| `script_capture_tools.py` | 545 |
| `query_usage_operations.py` | 519 |
| `validation_result_models.py` | 511 |
| `context_models.py` | 498 |

## Approach

For each file, identify logical split points (helpers, models, formatters, handlers) and extract cohesive submodules. Process in batches of 3-5 files per session, starting with the largest.

## Implementation Steps

1. **Batch 1** (largest 5): Split `compaction_operations.py`, `validation_operations.py`, `analysis_operations.py`, `roadmap_corruption.py`, `phase5_production_monitoring_helpers.py`
2. **Batch 2** (next 5): Split `task_locking.py`, `refactoring_operations.py`, `script_capture_tools.py`, `query_usage_operations.py`, `validation_result_models.py`
3. **Batch 3** (next 5): Split `context_models.py`, `models.py`, `plan_crud.py`, `phase1_foundation_rollback.py`, `pre_commit_tools.py`
4. **Batch 4** (remaining): Split remaining files exceeding 400 lines
5. **For each file**:
   a. Read file, identify logical groupings
   b. Extract helpers/models/formatters into new submodule
   c. Update imports in all dependent files
   d. Run `execute_pre_commit_checks` after each split
6. **Final verification**: `wc -l src/cortex/tools/*.py | awk '$1 > 400'` returns empty

## Dependencies

None (can proceed independently).

## Success Criteria

- Zero files in `src/cortex/tools/` exceed 400 lines
- All tests pass after each batch
- Type checks pass
- No functionality changes

## Testing Strategy

- **Coverage Target**: 95% — existing tests must continue passing; no new functionality added
- **Unit Tests**: Run full test suite after each batch split
- **Integration Tests**: Verify MCP tool registration still works
- **Regression**: `uv run pytest tests/ -q` passes after each batch

## Risks & Mitigation

- **Risk**: Import chain breakage → **Mitigation**: Update all imports; run type checker after each split
- **Risk**: Circular imports from split → **Mitigation**: Use forward references or restructure

## Timeline

4 sessions (~2 hours total), batched by size.
