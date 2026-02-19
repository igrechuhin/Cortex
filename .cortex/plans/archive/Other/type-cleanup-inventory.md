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

## 4. Per-File Drill-Down (Classification)

Classification key: **response** (tool/API return payload), **config** (user/config or storage payload), **metadata** (index/cache/version data), **report** (validation/analysis report).

### 4.1 Core

| File | Classification | Notes |
|------|----------------|-------|
| `core/metadata_index.py` | **metadata** | Index data, `_data`, file_meta, version_meta, `get_stats`, `get_dependency_graph`, `create_empty_index`; schema-validated JSON at boundary. |
| `core/cache_json_access.py` | **config** | Read/write payloads `dict[str, object] \| list[object]` for generic JSON cache storage. |
| `core/mcp_stability.py` | **config** | Uses `dict[str, Any]` for MCP-related payload (single usage). |
| `core/usage_context.py` | **config** | `dict[str, Any]` for current managers context (global context var). |

### 4.2 Managers

| File | Classification | Notes |
|------|----------------|-------|
| `managers/usage_tracker.py` | **metadata** / **response** | Event row dict, `generate_usage_event_id(data)`, `_ensure_event_id(item)`; append_event `list[object]` for event list. |

### 4.3 Tools

| File | Classification | Notes |
|------|----------------|-------|
| `tools/usage_analytics.py` | **metadata** | Event data, `_calls_key`/`calls_key` for sort keys. |
| `tools/script_capture_tools.py` | **response** | `_record_to_summary`, `_analysis_to_summary`, tool payload. |
| `tools/health_check_operations.py` | **report** | Payload from report dict. |
| `tools/cache_json_tools.py` | **config** | Payload for read/write cache JSON. |
| `tools/file_operation_helpers.py` | **response** | Return dict from helper. |
| `tools/file_operations.py` | **response** | Tool response payloads. |
| `tools/validation_operations.py` | **report** | Validation result payloads. |

### 4.4 Validation & Linking

| File | Classification | Notes |
|------|----------------|-------|
| `validation/validation_config.py` | **config** | `user_config_raw: dict[str, object]` for validation config. |
| `linking/link_validator.py` | **report** | Link dict, validation result (valid_links, broken_links, warnings), stats, report generation. |

### 4.5 Health Check & Analysis

| File | Classification | Notes |
|------|----------------|-------|
| `health_check/models.py` | **report** | TypedDicts for health-check report (MergeOpportunity, OptimizationOpportunity, *AnalysisResult, HealthCheckReport). |
| `health_check/tool_analyzer.py` | **report** | Tool descriptors and merge result dicts. |
| `health_check/dependency_mapper.py` | **metadata** | Dependency graph / map structures. |
| `analysis/insight_usage_org.py` | **response** / **report** | Insight/usage organization return and list of dicts. |

### 4.6 Script Detection

| File | Classification | Notes |
|------|----------------|-------|
| `script_detection/models.py` | **metadata** | `to_storage_dict` / `from_storage_dict` for script capture storage. |

### 4.7 Refactoring

| File | Classification | Notes |
|------|----------------|-------|
| `refactoring/rollback_execution.py` | **metadata** | `version_history_list` cast to `list[object]` (version history). |

---

## 5. Pydantic Candidates and Circular-Import Hotspots

### 5.1 High-Value Pydantic Candidates

1. **`health_check/models.py`**  
   Convert all TypedDicts to Pydantic `BaseModel`: `MergeOpportunity`, `OptimizationOpportunity`, `PromptAnalysisResult`, `RuleAnalysisResult`, `ToolAnalysisResult`, `HealthCheckReport`.  
   **Risk:** Low. No dependency on `core.models`; used by health_check modules and tools only.

2. **`linking/link_validator.py`**  
   Introduce `linking/models.py` (or `linking/report_models.py`) with: `LinkInfo`, `BrokenLink`, `LinkWarning`, `FileValidationResult`, `ValidationReport`.  
   **Risk:** Medium. `link_parser` returns dicts; validator consumes them. Keep parser output as dict or add a shared “link shape” model in `linking/models.py` to avoid circular link_parser ↔ link_validator.

3. **`validation/validation_config.py`**  
   User config: introduce a Pydantic model for the merged validation config (e.g. `ValidationUserConfig`) so `user_config_raw: dict[str, object]` becomes `ValidationUserConfig`.  
   **Risk:** Low.

4. **`script_detection/models.py`**  
   `ScriptCaptureRecord.from_storage_dict` / `to_storage_dict`: consider making the storage shape a Pydantic model (e.g. `ScriptCaptureStorageDict`) for validation and typing.  
   **Risk:** Low.

5. **Usage events (managers/tools)**  
   `usage_tracker` and `usage_analytics`: event row / event payload could become a Pydantic model (e.g. `UsageEventRow`, `UsageEventPayload`) in `managers/models.py` or a shared `usage/models.py`.  
   **Risk:** Low–medium. Ensure no cycle: managers → core, tools → managers/core.

### 5.2 Circular-Import Hotspots

- **`core/models.py`**  
  Already the central type hub. Used by: `metadata_index`, `refactoring/models`, `version_manager`, `dependency_graph`, `migration`. Keep it free of imports from tools, refactoring, or linking so it stays a leaf in the import graph.

- **`refactoring/models.py`**  
  Imports `cortex.core.models` (DictLikeModel, ModelDict). Do not import refactoring from core/models.

- **`linking`**  
  If `linking/models.py` is added, have it depend only on stdlib/pydantic; `link_parser` and `link_validator` can both depend on `linking/models.py`. Avoid `link_parser` importing `link_validator` or vice versa.

- **`metadata_index`**  
  Imports `core.models` (SectionMetadata). Index schema (file list, version history) could be expressed with Pydantic models in `core/models.py`; validate at boundary and keep internal index as dict until refactor of MetadataIndex is done.

---

## 6. First Draft: Model Groupings for Step 2 (Model Design)

Groupings for shared Pydantic models to be designed in Phase 53 Step 2:

| Group | Location | Candidates | Purpose |
|-------|----------|------------|---------|
| **Health check report** | `health_check/models.py` | MergeOpportunity, OptimizationOpportunity, *AnalysisResult, HealthCheckReport | Replace TypedDicts with BaseModel; used by tool_analyzer and health_check_operations. |
| **Linking / validation report** | `linking/models.py` (new) | LinkInfo, BrokenLink, LinkWarning, FileValidationResult, ValidationReport | Type link validator inputs/outputs and reports. |
| **Validation config** | `validation/models.py` or `validation_config.py` | ValidationUserConfig (merged config) | Type user_config_raw in ValidationConfig. |
| **Usage events** | `managers/models.py` or `usage/models.py` (new) | UsageEventPayload, UsageEventRow | Type usage_tracker and usage_analytics event data. |
| **Script capture storage** | `script_detection/models.py` | ScriptCaptureStorageDict (or extend ScriptCaptureRecord) | Type storage dict for script capture. |
| **Core index/metadata** | `core/models.py` | Optional: FileIndexEntry, VersionEntry (if migrating MetadataIndex internals) | Keep schema in core; add only if MetadataIndex is refactored to use models internally. |
| **Cache JSON** | Keep as-is or `core/models.py` | JsonDict/JsonList already in core; cache_json_access stays generic | No new model required unless we narrow cache value types. |

**Suggested implementation order for Step 2:**  

1) Health check models (TypedDict → BaseModel).  
2) Validation config model.  
3) Linking report models.  
4) Usage event models.  
5) Script capture storage model.  
6) Core index models only if/when refactoring MetadataIndex.
