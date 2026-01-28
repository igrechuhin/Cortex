# Type Cleanup Inventory (Phase 53)

**Date:** 2026-01-23  
**Source Plan:** `phase-53-type-safety-cleanup.md`  
**Scope:** Code under `src/cortex/`

---

## 1. Summary of Problematic Type Patterns

- **Return types**
  - `-> dict[str, object]`: 116 matches across 39 files
  - `-> list[object]`: 2 matches across 2 files
- **Parameters / locals**
  - `: dict[str, object]`: 298 matches across 57 files
  - `: list[object]`: 13 matches across 7 files
  - `: object`: 201 matches across 33 files
- **Other indicators**
  - `from __future__ import annotations`: 4 files
  - `TYPE_CHECKING`: 0 matches
  - `# pyright: ignore`: 0 matches
  - `TypedDict`: 5 matches across 4 files
  - `Any`: 22 matches across 10 protocol files

These counts are derived from ripgrep searches limited to `src/`.

---

## 2. Distribution by Area (High-Level)

- **Core**
  - `src/cortex/core/models.py`: heavy `: object` usage, central for manager and JSON types.
  - `src/cortex/core/container.py`: uses `: object` for container-managed instances.
  - `src/cortex/core/advanced_cache.py`, `token_counter.py`, `metadata_index.py`, `retry.py`, `cache.py`: use `: object` in cache and token-related structures.
  - `src/cortex/core/protocols/*`: `Any` is used in multiple protocol definitions.

- **Tools**
  - `src/cortex/tools/file_operations.py`, `phase5_execution.py`, `phase8_structure.py`, `phase4_*_operations.py`, `analysis_operations.py`, `synapse_prompts.py`, `pre_commit_tools.py`, `synapse_tools.py`, `configuration_operations.py`, `validation_*`, `transclusion_operations.py`:
    - Mix of `-> dict[str, object]`, `: dict[str, object]`, and `: list[object]` for tool request/response payloads.

- **Structure**
  - `src/cortex/structure/structure_manager.py`, `structure_lifecycle.py`, `template_manager.py`, `structure_migration.py`, `structure/lifecycle/setup.py`:
    - Use `-> dict[str, object]` and `: dict[str, object]` for structure and template metadata.

- **Refactoring**
  - `src/cortex/refactoring/refactoring_engine.py`, `refactoring_executor.py`, `reorganization_planner.py`, `reorganization/*`, `split_*`, `learning_*`, `consolidation_detector.py`, `adaptation_config.py`, `rollback_history_loader.py`:
    - Heavy use of `-> dict[str, object]`, `: dict[str, object]`, and `: object` for refactoring suggestions, plans, and learning data.

- **Rules**
  - `src/cortex/rules/synapse_manager.py`, `synapse_repository.py`, `rules_merger.py`, `rules_loader.py`, `prompts_loader.py`, `context_detector.py`:
    - Rely on `-> dict[str, object]`, `: dict[str, object]`, and `: object` for rule manifests, merged rule sets, and context analysis.

- **Optimization & Validation**
  - `src/cortex/optimization/optimization_config.py`, `context_optimizer.py`, `progressive_loader.py`, `summarization_engine.py`, `optimization_strategies.py`:
    - Use `-> dict[str, object]`, `: dict[str, object]`, and `: object` for optimization config and results.
  - `src/cortex/validation/validation_config.py`, `validation/models.py`, `schema_validator.py`:
    - Mix of `-> dict[str, object]`, `: dict[str, object]`, and `: object` for validation configuration and reports.

- **Analysis & Services**
  - `src/cortex/analysis/pattern_*`, `insight_*`, `analysis/models.py`, `insight_engine.py`, `insight_formatter.py`, `pattern_normalization.py`, `pattern_detection.py`, `pattern_analyzer.py`, `pattern_analysis.py`:
    - Use `-> dict[str, object]`, `: dict[str, object]`, `: list[object]`, and `: object` for pattern and insight data.
  - `src/cortex/services/models.py`:
    - Contains `TypedDict` usage for service-related shapes.

---

## 3. Prioritized Modules for Refactor

Based on the inventory and the Phase 53 plan, the following areas should be addressed first:

1. **Core type hubs**
   - `src/cortex/core/models.py`
   - `src/cortex/managers/types.py`
   - `src/cortex/core/protocols/*` (especially those using `Any` and `object`)

2. **High-traffic tools**
   - `src/cortex/tools/file_operations.py`
   - `src/cortex/tools/phase5_execution.py`
   - `src/cortex/tools/phase8_structure.py`
   - `src/cortex/tools/phase4_*_operations.py`

3. **Refactoring pipeline**
   - `src/cortex/refactoring/refactoring_engine.py`
   - `src/cortex/refactoring/refactoring_executor.py`
   - `src/cortex/refactoring/reorganization_planner.py`
   - `src/cortex/refactoring/reorganization/*`

4. **Rules and structure management**
   - `src/cortex/rules/*` (loader/merger/synapse modules)
   - `src/cortex/structure/*` (manager/lifecycle/templates/migration)

5. **Optimization, validation, and analysis**
   - `src/cortex/optimization/*`
   - `src/cortex/validation/*`
   - `src/cortex/analysis/*`

This priority ordering aligns with the plan’s focus on core modules and tools first, followed by rules and services.

---

## 4. Next Inventory Actions

- Drill down per file to:
  - Classify each `dict[str, object]` usage as **response**, **config**, **metadata**, or **report**.
  - Identify candidates for shared Pydantic models (to be extracted into `core/models/`, `tools/models/`, `refactoring/models/`, etc.).
  - Flag potential circular import hotspots where shared types must be moved into dedicated model modules.
- Prepare a first draft of model groupings based on these classifications to feed directly into Step 2 (model design).
