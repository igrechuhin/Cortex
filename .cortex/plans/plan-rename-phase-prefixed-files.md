# Rename Phase-Prefixed Tool Files to Functional Names

**Status**: PENDING
**Priority**: MEDIUM
**Created**: 2026-02-28
**Type**: Refactoring
**Effort**: Large (multi-session)

## Goal

Rename 47 phase-numbered files in `src/cortex/tools/` (e.g., `phase4_context_operations.py`) to functional names (e.g., `context_operations.py`), eliminating confusing historical naming.

## Context

47 files use phase-numbered prefixes (`phase1_`, `phase4_`, `phase5_`, `phase8_`). These reflect historical roadmap phases, not functional purpose:

- Phase numbers confuse new developers ("What is phase4?")
- No runtime purpose (tools aren't conditionally loaded by phase)
- Skip numbers (no phase2, phase3, phase6, phase7) reveal non-sequential history

Breakdown: `phase1_` (5 files), `phase2_` (1), `phase3_` (1), `phase4_` (11), `phase5_` (26), `phase8_` (4).

## Approach

Create a rename mapping, then batch-rename by phase prefix. Update all imports project-wide after each batch.

## Implementation Steps

1. **Create rename mapping**:
   - `phase1_foundation_*` → `foundation_*`
   - `phase2_linking.py` → `linking_operations.py`
   - `phase3_validation.py` → `validation_tools.py`
   - `phase4_context_*` → `context_*`
   - `phase4_optimization_*` → `optimization_*`
   - `phase4_progressive_*` → `progressive_*`
   - `phase4_relevance_*` → `relevance_*`
   - `phase4_summarization_*` → `summarization_*`
   - `phase4_metadata_*` → `metadata_*`
   - `phase4_hybrid_*` → `hybrid_*`
   - `phase5_analysis*` → `analysis_*` (resolve conflicts with existing `analysis_operations.py`)
   - `phase5_evaluation*` → `evaluation_*`
   - `phase5_execution*` → `execution_*`
   - `phase5_refactoring*` → (use `refactoring_tools_*` to avoid conflict with `refactoring/` module)
   - `phase5_*_helpers.py` → `*_helpers.py` (drop prefix)
   - `phase8_structure*` → `structure_*`
2. **Check for naming conflicts** with existing non-phase files
3. **Batch 1**: Rename all `phase1_` files (8 files) ✅ — done 2026-03-01; update imports, run tests
4. **Batch 2**: Rename all `phase4_` files (11 files), update imports, run tests
5. **Batch 3**: Rename all `phase5_` files (26 files), update imports, run tests
6. **Batch 4**: Rename `phase2_`, `phase3_`, `phase8_` files (6 files), update imports, run tests
7. **Update `__init__.py`** exports after all renames
8. **Final verification**: `ls src/cortex/tools/phase*.py` returns empty

## Dependencies

- Should be done after `plan-tools-file-size-violations.md` to avoid double-touching files

## Success Criteria

- Zero files with `phase*_` prefix in `src/cortex/tools/`
- All tests pass
- All imports resolve
- Type checks pass

## Testing Strategy

- **Coverage Target**: 95% — existing tests must continue passing; no new functionality
- **Unit Tests**: Full test suite after each batch
- **Integration Tests**: MCP tool registration verification
- **Regression**: `uv run pytest tests/ -q` and `uv run pyright src/` pass after each batch

## Risks & Mitigation

- **Risk**: Mass import breakage → **Mitigation**: Use IDE refactoring tools; batch by phase prefix
- **Risk**: Naming conflicts → **Mitigation**: Pre-check all target names in step 2

## Timeline

4 sessions (~3 hours total), batched by phase prefix.
