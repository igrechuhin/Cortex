# Reorganize tools/ Into Domain Sub-Packages

**Status**: PENDING
**Priority**: LOW
**Created**: 2026-02-28
**Type**: Architecture refactoring
**Effort**: Very large (multi-session)

## Goal

Reorganize the flat `src/cortex/tools/` directory (185 files) into domain sub-packages for improved navigation and maintainability.

## Context

`src/cortex/tools/` contains 185 files in a flat directory, making navigation difficult and obscuring domain boundaries. Other modules (`refactoring/`, `optimization/`, `validation/`) are well-organized into sub-packages already.

## Approach

Create sub-packages by functional domain, move files, update all imports.

## Implementation Steps

1. **Design sub-package boundaries** (proposed structure):

   ```text
   src/cortex/tools/
   ├── __init__.py          (tool registration, exports)
   ├── models.py            (shared tool models)
   ├── context/             (context operations, analysis)
   ├── evaluation/          (evaluation, benchmarks)
   ├── execution/           (pre-commit, quality)
   ├── files/               (CRUD, sections, metadata)
   ├── linking/             (links, transclusion)
   ├── memory/              (memory bank, compaction)
   ├── optimization/        (progressive loading, relevance)
   ├── plans/               (plan CRUD, roadmap, archiving)
   ├── session/             (session start, health, registry)
   ├── structure/           (project structure)
   ├── synapse/             (rules, prompts)
   ├── usage/               (analytics, tracking)
   └── validation/          (schema, quality, timestamps)
   ```

2. **Create sub-packages** with `__init__.py` files
3. **Move files by domain** (one domain per session):
   - Session 1: `context/` (context_*, analysis_*) ✅ COMPLETE (2026-03-01)
   - Session 2: `plans/` (plan_*, roadmap_*)
   - Session 3: `files/` (file_*, markdown_*)
   - Session 4: `execution/` (pre_commit_*, quality_*)
   - Session 5: `optimization/` (progressive_*, relevance_*, summarization_*)
   - Session 6: `validation/` (validation_*, schema_*)
   - Session 7: `session/`, `linking/`, `synapse/`, `usage/`, `structure/`
   - Session 8: `evaluation/`, `memory/`, remaining files
4. **Update all imports** project-wide after each move
5. **Update `__init__.py`** exports
6. **Run full test suite** after each session

## Dependencies

- **MUST complete first**: `plan-tools-file-size-violations.md`
- **MUST complete first**: `archive/Other/plan-rename-phase-prefixed-files.md` (COMPLETE)

## Success Criteria

- `ls src/cortex/tools/*.py | wc -l` is under 10 (shared files only)
- All tests pass
- Import paths are clean and domain-organized
- Type checks pass

## Testing Strategy

- **Coverage Target**: 95% — existing tests must continue passing; no new functionality
- **Unit Tests**: Full test suite after each session
- **Integration Tests**: MCP tool registration, server startup
- **Regression**: `uv run pytest tests/ -q` and `uv run pyright src/` pass after each session

## Risks & Mitigation

- **Risk**: Massive import chain changes → **Mitigation**: One domain at a time; full tests between moves
- **Risk**: Circular imports → **Mitigation**: Careful dependency analysis before moving

## Timeline

8 sessions (~6 hours total), one domain per session.
