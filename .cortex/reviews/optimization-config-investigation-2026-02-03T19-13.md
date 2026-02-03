# End-of-Session Analysis: Optimization Config Investigation

## Summary

Investigation of `.cortex/config/optimization.json` shows that **many properties are never read at runtime**. The config is loaded and merged with defaults, and the `configure` tool (VIEW) exposes the full dict to clients, but only a subset of keys is used when creating managers or driving behavior. This report lists **used** vs **unused** properties and recommends either wiring the unused ones or documenting/removing them.

---

## Context Effectiveness Analysis

**Sessions Analyzed**: N/A (investigation task, no `load_context` session data).  
**Calls Analyzed**: 0  

No session logs were used for this run. For context-effectiveness metrics, use `load_context()` at task start and re-run analysis later.

---

## Optimization.json: Properties That Do Nothing

### Method

- Traced every key in `optimization.json` and `DEFAULT_OPTIMIZATION_CONFIG` to:
  - `OptimizationConfig` getters and `get(key_path)` call sites
  - Manager constructors (`manager_initialization.py`, `container_factory.py`)
  - Rules/synapse/summarization/context/self_evolution usage
- **Used** = value (or a derived value) is read and passed into some component that affects behavior.
- **Unused** = only stored/validated/serialized; no runtime reader.

---

### 1. Top-level

| Property   | Used? | Notes |
|-----------|-------|--------|
| `enabled` | **No** | No code checks `config["enabled"]` or `optimization_config.get("enabled")`. Optimization is always active. |

---

### 2. `token_budget`

| Property            | Used? | Notes |
|---------------------|-------|--------|
| `default_budget`    | **Yes** | `get_token_budget()` → `load_context`, `load_progressive_context`, ProgressiveLoader (via phase4 ops and container_factory). |
| `max_budget`        | **No** | `get_max_token_budget()` exists but is **never called**. Only `get_token_budget()` (default_budget) is used. |
| `reserve_for_response` | **No** | No getter in `OptimizationConfig`. Only in default dict and `TokenBudgetOptConfigModel`. Never read. |

---

### 3. `loading_strategy`

| Property          | Used? | Notes |
|-------------------|-------|--------|
| `default`         | **No** | `get_loading_strategy()` exists but is **never called**. ProgressiveLoader/ContextOptimizer do not receive loading strategy from config. |
| `mandatory_files` | **Yes** | `get_mandatory_files()` → ContextOptimizer, ProgressiveLoader (manager_initialization, container_factory). |
| `priority_order`  | **Yes** | `get_priority_order()` → `load_progressive_context` (phase4_progressive_operations). |

---

### 4. `summarization`

| Property                 | Used? | Notes |
|--------------------------|-------|--------|
| `enabled`                | **No** | `is_summarization_enabled()` exists but is **never called**. SummarizationEngine is created without config; tool args drive behavior. |
| `auto_summarize_old_files` | **No** | No getter; never read. |
| `age_threshold_days`    | **No** | No getter; never read. |
| `target_reduction`       | **No** | `get_summarization_target_reduction()` exists but is **never called**. Tool `summarize_content` takes reduction as argument. |
| `strategy`               | **No** | `get_summarization_strategy()` exists but is **never called**. Tool takes strategy as argument. |
| `cache_summaries`       | **No** | No getter; never read. SummarizationEngine uses its own cache path, not config. |

**Entire block**: Stored and validated only. No runtime behavior is driven by it.

---

### 5. `relevance`

| Property            | Used? | Notes |
|---------------------|-------|--------|
| `keyword_weight`    | **Yes** | `get_relevance_weights()` → RelevanceScorer (manager_initialization, container_factory). |
| `dependency_weight` | **Yes** | Same. |
| `recency_weight`    | **Yes** | Same. |
| `quality_weight`    | **Yes** | Same. |

All four weights are used.

---

### 6. `performance`

| Property            | Used? | Notes |
|---------------------|-------|--------|
| `cache_enabled`     | **No** | `is_cache_enabled()` and `get_cache_ttl()` exist but are **never called**. TransclusionEngine is created with hardcoded `cache_enabled=True`. No component receives these from config. |
| `cache_ttl_seconds` | **No** | Same; no reader. |
| `max_cache_size_mb` | **No** | No getter in OptimizationConfig; never read. |

---

### 7. `rules`

| Property                  | Used? | Notes |
|---------------------------|-------|--------|
| `enabled`                 | **Yes** | `is_rules_enabled()` → RulesManager creation, rules tool checks. |
| `rules_folder`           | **Yes** | `get_rules_folder()` → RulesManager. |
| `reindex_interval_minutes`| **Yes** | `get_rules_reindex_interval()` → RulesManager. |
| `auto_include_in_context`| **No** | `is_rules_auto_include()` exists but is **never called**. |
| `max_rules_tokens`        | **Yes** | `get_rules_max_tokens()` → rules_operation_helpers (resolve_config_defaults) → get_relevant_rules. |
| `min_relevance_score`     | **Yes** | `get_rules_min_relevance()` → same. |
| `rule_priority`          | **No** | RulesManager.get_relevant_rules(rule_priority=...) is always called with default or tool arg. Rules tool does **not** pass optimization_config rule_priority; synapse_tools passes tool arg. Config value never read. |
| `context_aware_loading`  | **No** | Not passed from config; get_relevant_rules(context_aware=True) is default. |
| `always_include_generic`  | **No** | No getter; never read. |
| `context_detection`       | **No** | Entire subtree unused. ContextDetector uses hardcoded `_get_language_keywords()` in context_detector.py; it does **not** read `rules.context_detection` or `rules.context_detection.language_keywords`. |

---

### 8. `synapse`

| Property              | Used? | Notes |
|-----------------------|-------|--------|
| `enabled`             | **Yes** | Checked indirectly (e.g. SynapseManager creation gated by structure/setup). |
| `synapse_folder`      | **Yes** | `get_synapse_folder()` → SynapseManager. |
| `synapse_repo`        | **No** | `get_synapse_repo()` exists but is **never called**. SynapseManager(project_root, synapse_folder) only. |
| `auto_sync`           | **No** | `is_synapse_auto_sync()` exists but is **never called**. |
| `sync_interval_minutes` | **No** | `get_synapse_sync_interval()` exists but is **never called**. |

---

### 9. `self_evolution`

| Property                    | Used? | Notes |
|-----------------------------|-------|--------|
| `enabled`                   | **No** | `is_self_evolution_enabled()` exists but is **never called**. |
| `analysis.track_usage_patterns`  | **No** | `is_usage_tracking_enabled()` exists but is **never called**. |
| `analysis.pattern_window_days`   | **No** | `get_pattern_window_days()` exists but is **never called**. |
| `analysis.min_access_count`      | **No** | `get_min_access_count()` exists but is **never called**. PatternAnalyzer uses its own default. |
| `analysis.track_task_patterns`   | **No** | `is_task_tracking_enabled()` exists but is **never called**. |
| `insights.auto_generate`     | **No** | `is_auto_insights_enabled()` exists but is **never called**. |
| `insights.min_impact_score` | **No** | `get_min_impact_score()` exists but is **never called**. |
| `insights.categories`      | **No** | `get_insight_categories()` exists but is **never called**. |

Note: `container_factory` uses `optimization_config.get("self_evolution.learning", {})`, `get("self_evolution.suggestions.min_confidence", 0.7)`, etc. Those paths are **not** in optimization.json (they belong to AdaptationConfig / refactoring schema). The `self_evolution` block in optimization.json (enabled, analysis, insights) has **no readers** in the codebase.

---

## Summary Table: Used vs Unused

| Section           | Used | Unused |
|-------------------|------|--------|
| Top-level         | 0    | 1 (`enabled`) |
| token_budget      | 1    | 2 (`max_budget`, `reserve_for_response`) |
| loading_strategy  | 2    | 1 (`default`) |
| summarization     | 0    | 6 (entire block) |
| relevance         | 4    | 0 |
| performance       | 0    | 3 (entire block) |
| rules             | 5    | 5+ (rule_priority, context_aware_loading, always_include_generic, entire context_detection) |
| synapse           | 2    | 3 (`synapse_repo`, `auto_sync`, `sync_interval_minutes`) |
| self_evolution    | 0    | 8 (enabled + analysis.*+ insights.*) |

Roughly **half** of the properties in optimization.json have no effect on runtime behavior.

---

## Recommendations

1. **Wire or drop**
   - Either connect the unused properties to real behavior (e.g. `get_loading_strategy()` into ProgressiveLoader, `performance.cache_*` into TransclusionEngine/MetadataIndex, `rules.context_detection.language_keywords` into ContextDetector, synapse sync interval into SynapseManager, self_evolution analysis/insights into PatternAnalyzer/InsightEngine), or remove/deprecate them and document that they are reserved for future use.

2. **Top-level `enabled`**
   - If kept, gate optimization features (e.g. context loading, summarization) on it; otherwise remove or document as “reserved.”

3. **token_budget**
   - Use `max_budget` where a cap is needed (e.g. load_context), or remove. Use or drop `reserve_for_response` (e.g. when computing effective budget).

4. **summarization**
   - Pass `enabled`, `target_reduction`, `strategy`, and optionally `cache_summaries`/`age_threshold_days` into SummarizationEngine or the summarize_content flow so config drives defaults; otherwise document as tool-arg-only.

5. **performance**
   - Pass `cache_enabled` and `cache_ttl_seconds` (and optionally `max_cache_size_mb`) into components that cache (e.g. TransclusionEngine, any cache layer) or remove from config.

6. **rules**
   - Pass `rule_priority`, `context_aware_loading`, and `always_include_generic` from config into `get_relevant_rules` call sites. Load `context_detection.language_keywords` from config in ContextDetector (or a single source of truth) instead of hardcoding in context_detector.py.

7. **synapse**
   - Use `synapse_repo`, `auto_sync`, and `sync_interval_minutes` in SynapseManager (or sync logic) if auto-sync is desired; otherwise remove or document.

8. **self_evolution**
   - Use analysis/insights settings in PatternAnalyzer, InsightEngine, or usage-tracking code; or move these under a different config (e.g. adaptation) and document. Otherwise remove from optimization.json to avoid confusion.

---

## Report Location

Saved to: `/Users/i.grechukhin/Repo/Cortex/.cortex/reviews/optimization-config-investigation-2026-02-03T19-13.md`

---

## Improvements Plan

Recommendation: Create an improvements plan (e.g. via Plan prompt) to wire or remove unused optimization.json properties so config and behavior stay in sync. No plan file was created in this run; run the Plan prompt with this report as input if you want a tracked plan.
