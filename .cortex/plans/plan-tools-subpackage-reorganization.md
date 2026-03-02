# Reorganize tools/ Into Domain Sub-Packages

**Status**: IN PROGRESS (Session 19 done)
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
   ├── config/              (configuration status, configure tool)
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
   - Session 2: `plans/` (plan_*, roadmap_*) ✅ COMPLETE (2026-03-01)
   - Session 3: `files/` (file_*, markdown_*) ✅ COMPLETE (2026-03-01)
   - Session 4: `execution/` (pre_commit_*, quality_*) ✅ COMPLETE (2026-03-01)
   - Session 5: `optimization/` (progressive_*, relevance_*, summarization_*) ✅ COMPLETE (2026-03-01)
   - Session 6: `validation/` (validation_*, schema_*) ✅ COMPLETE (2026-03-01)
   - Session 7: `session/`, `linking/`, `synapse/`, `usage/`, `structure/` ✅ COMPLETE (2026-03-01)
   - Session 8: `evaluation/`, `memory/`, remaining files ✅ COMPLETE (2026-03-02)
   - Session 9: `session/` — moved connection_health, session_models, health_connection_models ✅ COMPLETE (2026-03-02)
   - Session 10: `execution/` — moved execution_errors, execution_feedback, execution_handlers, execution_helpers, execution_monitoring, execution_planning, execution_validation ✅ COMPLETE (2026-03-02)
   - Session 11: `config/` — moved config_status, configuration_helpers, configuration_hybrid, configuration_operations, configuration_operations_errors, configuration_operations_handlers, configuration_operations_response ✅ COMPLETE (2026-03-02)
   - Session 12: `refactoring/` — moved refactoring_operation_concise, refactoring_operation_helpers, refactoring_operations, refactoring_operations_docs, refactoring_result_models, refactoring_tools ✅ COMPLETE (2026-03-02)
   - Session 13: `optimization/` — moved optimization_handlers, optimization_handlers_load, optimization_handlers_validation, optimization_handlers_format; `usage/` — moved query_usage_operations, query_usage_handlers, query_usage_models ✅ COMPLETE (2026-03-02)
   - Session 14: `session/` — moved task_locking, task_locking_handlers, task_locking_helpers, health_check_operations ✅ COMPLETE (2026-03-02)
   - Session 15: `usage/` — moved production_monitoring_*, redundancy_helpers, token_efficiency_helpers, tool_frequency_helpers ✅ COMPLETE (2026-03-02)
   - Session 16: `files/` — moved file_operations_models, markdown_models to files/ ✅ COMPLETE (2026-03-02). Resolved circular imports via lazy imports in plans/completion_ops, plans/entries, plans/entries_insert, plans/entries_removal.
   - Session 17: `execution/` — moved error_formatters, error_formatters_core, error_formatters_domain ✅ COMPLETE (2026-03-02). Updated imports in config, validation, synapse, files, refactoring, optimization, execution. 4867 tests, 92.32% coverage.
   - Session 18: `execution/` — moved feedback_models, workflow_models, workflow_operations, composite_tools. Added composite_tools shim at tools root for backward compat. Flat files: 24→21. 4867 tests, 92.32% coverage.
   - Session 19: `structure/` — moved tool_search_operations to structure/tool_search.py; created `skill_pack/` subpackage (models, operations). Flat files: 21→18. 4867 tests, 92.32% coverage.

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
