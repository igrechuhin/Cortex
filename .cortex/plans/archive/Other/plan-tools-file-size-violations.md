# Fix Tool Files Exceeding 400-Line Limit

**Status**: COMPLETE
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
| `compaction_operations.py` | 110 (split into handoff, write_helpers) |
| `validation_operations.py` | 620 |
| `analysis_operations.py` | 598 |
| `roadmap_corruption.py` | 586 |
| `phase5_production_monitoring_helpers.py` | 314 (split: models, metrics, drift) |
| `task_locking.py` | 572 |
| `refactoring_operations.py` | 150 (split: refactoring_operations_docs.py) |
| `script_capture_tools.py` | 368 (split: script_capture_helpers, script_capture_handlers) |
| `query_usage_operations.py` | <400 (split: query_usage_models) |
| `validation_result_models.py` | 365 (split: validation_result_links_models) |
| `context_models.py` | 498 |

## Approach

For each file, identify logical split points (helpers, models, formatters, handlers) and extract cohesive submodules. Process in batches of 3-5 files per session, starting with the largest.

## Implementation Steps

1. **Batch 1** (largest 5): Split `compaction_operations.py` ✅, `validation_operations.py` ✅ (validation_response_formatters.py), `analysis_operations.py` ✅ (analysis_run_helpers.py), `roadmap_corruption.py` ✅ (roadmap_corruption_models.py, roadmap_corruption_detectors.py, roadmap_corruption_helpers.py), `phase5_production_monitoring_helpers.py` ✅ (phase5_production_monitoring_models.py, phase5_production_monitoring_metrics.py, phase5_production_monitoring_drift.py)
2. **Batch 2** (next 5): Split `task_locking.py` ✅ (task_locking_helpers.py, task_locking_handlers.py), `refactoring_operations.py` ✅ (refactoring_operations_docs.py), `script_capture_tools.py` ✅ (script_capture_helpers.py, script_capture_handlers.py), `query_usage_operations.py` ✅ (query_usage_models.py), `validation_result_models.py` ✅ (validation_result_links_models.py)
3. **Batch 3** (next 5): Split `context_models.py` ✅ (context_auxiliary_models.py), `models.py` ✅ (models_reexports.py), `plan_crud.py` ✅ (plan_crud_models.py, plan_crud_helpers.py), `phase1_foundation_rollback.py` ✅ (phase1_foundation_rollback_models.py, phase1_foundation_rollback_helpers.py), `pre_commit_tools.py` ✅ (pre_commit_tools_run_helpers.py)
4. **Batch 4** (remaining): Split query_usage_operations.py ✅ (query_usage_handlers.py), tool_error_formatters.py ✅ (tool_error_formatters_core.py, tool_error_formatters_domain.py), plan_roadmap.py ✅ (plan_roadmap_helpers.py, plan_roadmap_models.py), link_graph_operations ✅ (link_graph_formatters.py), phase4_metadata_helpers ✅ (phase4_metadata_logging_helpers.py), session_brief ✅ (session_brief_extraction_helpers.py), transclusion_operations ✅ (transclusion_response_helpers.py), refactoring_operation_helpers ✅ (refactoring_operation_concise.py), phase5_execution ✅ (phase5_execution_feedback.py), pre_commit_pipeline ✅ (pre_commit_pipeline_processors.py, pre_commit_pipeline_quality.py), phase1_foundation_stats ✅ (phase1_foundation_stats_helpers.py), file_operation_helpers ✅ (file_operation_error_responses.py)
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
