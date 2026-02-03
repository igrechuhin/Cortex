# Wire optimization.json to Runtime Behavior

**Status**: PENDING  
**Created**: 2026-02-03  
**Source**: `.cortex/reviews/optimization-config-investigation-2026-02-03T19-13.md`  
**Priority**: Medium

## Goal

Connect all properties in `.cortex/config/optimization.json` to actual runtime behavior, or explicitly remove unused ones, so config and behavior stay in sync. The investigation found roughly half of the properties are never read; this plan addresses each unused section.

## Context

- **Investigation**: End-of-session analysis traced every key in optimization.json to OptimizationConfig getters and manager constructors. Many properties (top-level `enabled`, token_budget.max_budget/reserve_for_response, loading_strategy.default, entire summarization/performance blocks, rules.rule_priority/context_detection, synapse.synapse_repo/auto_sync/sync_interval_minutes, entire self_evolution block) have no readers.
- **Impact**: Users editing optimization.json cannot influence behavior for those keys; config appears to do more than it does.
- **Options per section**: (1) Wire — pass config into components that should respect it; or (2) Remove/deprecate — drop from config and document, or document as "reserved for future use."

## Dependencies

- Existing OptimizationConfig getters (many already exist but are uncalled).
- Manager initialization (`manager_initialization.py`, `container_factory.py`) and tool call sites (phase4, rules_operations, synapse_tools).

## Implementation Steps

Implementation order: start with low-risk, high-clarity wiring (token_budget, loading_strategy), then summarization/performance, then rules/synapse/self_evolution, and finally top-level `enabled` if kept.

### Step 1: Token budget — wire max_budget and reserve_for_response

**Target**: `OptimizationConfig`, `load_context` / `load_progressive_context` (phase4), ProgressiveLoader/ContextOptimizer if they need a cap.

**Tasks**:

1. **Use `get_max_token_budget()`**: Where a token cap is needed (e.g. `load_context`, `load_progressive_context`, or ContextOptimizer), pass `min(requested_budget, optimization_config.get_max_token_budget())` so `token_budget.max_budget` is enforced.
2. **Add getter for `reserve_for_response`**: In `OptimizationConfig`, add `get_reserve_for_response() -> int` reading `token_budget.reserve_for_response` (default 10000).
3. **Apply reserve in budget calculation**: When computing effective budget for context loading, subtract `get_reserve_for_response()` from the cap so the response has room (e.g. `effective_budget = min(budget, get_max_token_budget()) - get_reserve_for_response()`). Ensure call sites (phase4_context_operations, phase4_progressive_operations) use this effective budget where appropriate.

**Acceptance**: `max_budget` and `reserve_for_response` are read and applied in context-loading code paths; unit tests assert config values affect budget.

### Step 2: Loading strategy — wire default strategy

**Target**: ProgressiveLoader and/or ContextOptimizer; `OptimizationConfig.get_loading_strategy()`.

**Tasks**:

1. **Pass loading strategy into loader/optimizer**: In manager_initialization (and container_factory if used), when creating ProgressiveLoader or ContextOptimizer, pass `loading_strategy=optimization_config.get_loading_strategy()`.
2. **Use strategy in loader/optimizer**: In ProgressiveLoader and/or ContextOptimizer, accept a `loading_strategy` parameter and branch behavior (e.g. "priority" vs "dependency_aware" vs "section_level" vs "hybrid") if not already present. If the type only supports one strategy today, document the others as reserved or add minimal branching.
3. **Tests**: Unit tests for OptimizationConfig.get_loading_strategy(); integration or unit tests that changing config changes loader behavior when multiple strategies are implemented.

**Acceptance**: `loading_strategy.default` is read and passed into the component(s) that perform loading; behavior reflects config or is documented as reserved.

### Step 3: Summarization — wire config as defaults for SummarizationEngine and tool

**Target**: SummarizationEngine constructor, `summarize_content` tool (phase4_summarization_operations).

**Tasks**:

1. **SummarizationEngine**: Add optional parameters (e.g. `enabled`, `target_reduction`, `strategy`, `cache_summaries`, `age_threshold_days`, `auto_summarize_old_files`) to SummarizationEngine constructor, defaulting from config when created in manager_initialization. Pass optimization_config into _create_summarization_engine and set these from `is_summarization_enabled()`, `get_summarization_target_reduction()`, `get_summarization_strategy()`, and new getters for `cache_summaries` / `age_threshold_days` / `auto_summarize_old_files`.
2. **summarize_content tool**: When tool args (target_reduction, strategy) are omitted or None, use config defaults from optimization_config (target_reduction, strategy). Optionally gate tool on `is_summarization_enabled()` (return friendly message when disabled).
3. **Getters**: Add getters in OptimizationConfig for summarization.cache_summaries, age_threshold_days, auto_summarize_old_files if not present.
4. **Tests**: Unit tests for config-driven defaults; test that tool uses config when args omitted.

**Acceptance**: summarization.enabled, target_reduction, strategy (and optionally cache_summaries, age_threshold_days, auto_summarize_old_files) drive SummarizationEngine and/or tool defaults.

### Step 4: Performance — wire cache_enabled and cache_ttl (and optional max_cache_size_mb)

**Target**: TransclusionEngine, any other cache-using component (e.g. MetadataIndex if it has cache settings).

**Tasks**:

1. **TransclusionEngine**: In manager_initialization (and container_factory), stop hardcoding `cache_enabled=True`. Pass `cache_enabled=optimization_config.is_cache_enabled()` and `cache_ttl_seconds=optimization_config.get_cache_ttl()` into TransclusionEngine constructor. Extend TransclusionEngine to accept and use cache_ttl if it currently does not.
2. **max_cache_size_mb**: Add `get_max_cache_size_mb() -> int` in OptimizationConfig. If any component (e.g. a cache layer) supports a size cap, pass this in; otherwise document as reserved or leave unused with a comment.
3. **Tests**: Unit tests that TransclusionEngine respects cache_enabled and cache_ttl when provided; config tests for performance block.

**Acceptance**: performance.cache_enabled and performance.cache_ttl_seconds are read and passed into TransclusionEngine (or equivalent); behavior reflects config.

### Step 5: Rules — wire rule_priority, context_aware_loading, always_include_generic; load context_detection from config

**Target**: rules_operations (handle_get_relevant_operation), synapse_tools_helpers (execute_rules_with_context), RulesManager.get_relevant_rules; ContextDetector.

**Tasks**:

1. **rule_priority and context_aware**: In rules_operations.handle_get_relevant_operation and synapse_tools_helpers.execute_rules_with_context, when calling rules_manager.get_relevant_rules, pass `rule_priority=optimization_config.get_rule_priority()` and `context_aware=optimization_config.is_context_aware_loading()` (add getters if missing: get_rule_priority(), is_context_aware_loading()). Tool args may still override when explicitly provided.
2. **always_include_generic**: Add getter `is_always_include_generic() -> bool` if missing. Pass into RulesManager.get_relevant_rules or RulesManager constructor if the API supports it; otherwise document as reserved.
3. **context_detection.language_keywords**: In ContextDetector, replace hardcoded `_get_language_keywords()` with loading from config. Inject OptimizationConfig (or a rules config provider) into ContextDetector; read `rules.context_detection.language_keywords` (and optionally enabled, detect_from_task, detect_from_files). Preserve fallback to current hardcoded dict if config missing or key absent.
4. **Tests**: Unit tests for get_rule_priority, is_context_aware_loading; integration or unit test that rules tool uses config for rule_priority and context_aware; test ContextDetector uses config language_keywords when available.

**Acceptance**: rules.rule_priority, context_aware_loading, and context_detection.language_keywords (at least) are read and affect get_relevant_rules and context detection; always_include_generic wired or documented.

### Step 6: Synapse — wire synapse_repo, auto_sync, sync_interval_minutes

**Target**: SynapseManager constructor and any sync scheduler.

**Tasks**:

1. **SynapseManager**: Extend SynapseManager constructor to accept `synapse_repo: str | None`, `auto_sync: bool`, `sync_interval_minutes: int`. In manager_initialization._create_synapse_manager, pass `optimization_config.get_synapse_repo()`, `optimization_config.is_synapse_auto_sync()`, `optimization_config.get_synapse_sync_interval()`.
2. **Sync behavior**: If auto_sync is True and a sync scheduler or background task exists, use sync_interval_minutes; otherwise document that these control future auto-sync behavior or a one-off sync API. If no scheduler exists, document as reserved.
3. **Tests**: Unit tests that SynapseManager receives and stores these values; optional integration test for sync interval if scheduler is implemented.

**Acceptance**: synapse.synapse_repo, auto_sync, and sync_interval_minutes are read and passed into SynapseManager (and used by sync logic if present).

### Step 7: Self-evolution — wire analysis and insights settings

**Target**: PatternAnalyzer, InsightEngine, usage-tracking or analysis call sites.

**Tasks**:

1. **Analysis settings**: Where PatternAnalyzer (or equivalent) is created or invoked, pass `pattern_window_days=optimization_config.get_pattern_window_days()`, `min_access_count=optimization_config.get_min_access_count()`, and honor `is_usage_tracking_enabled()` and `is_task_tracking_enabled()` (e.g. skip tracking when disabled). Ensure manager_initialization/container_factory pass optimization_config into the component that uses these.
2. **Insights settings**: Where InsightEngine (or get_insights-style logic) is invoked, pass `min_impact_score=optimization_config.get_min_impact_score()`, `categories=optimization_config.get_insight_categories()`, and honor `is_auto_insights_enabled()`.
3. **Top-level self_evolution.enabled**: Gate creation or invocation of analysis/insights components on `optimization_config.is_self_evolution_enabled()` where appropriate.
4. **Tests**: Unit tests that config values are read and passed; tests that disabling self_evolution or analysis/insights reduces or skips the corresponding behavior.

**Acceptance**: self_evolution.enabled, analysis.*, and insights.* are read and affect PatternAnalyzer, InsightEngine, and/or usage-tracking behavior.

### Step 8: Top-level enabled — gate optimization features

**Target**: Phase4 tools (load_context, load_progressive_context, summarize_content), optionally others that are purely "optimization" (e.g. get_relevance_scores).

**Tasks**:

1. **Define scope**: Decide which tools/features are "optimization" and gated by top-level `enabled` (e.g. load_context, load_progressive_context, summarize_content, get_relevance_scores). Add `is_optimization_enabled()` or use `config.get("enabled", True)` in OptimizationConfig if not present.
2. **Gate tools**: At the start of each gated tool handler, if `not optimization_config.get("enabled", True)`, return a friendly JSON/result indicating optimization is disabled and no work was done.
3. **Tests**: Unit tests that when enabled=false, gated tools return disabled message without performing work.

**Acceptance**: Top-level `enabled` is read and gates the agreed optimization tools.

## Testing Strategy

- **Coverage target**: Minimum 95% for new/updated code paths (config getters, constructor args, gating branches).
- **Unit tests**:
  - OptimizationConfig: every new or previously uncalled getter (max_budget, reserve_for_response, loading_strategy, summarization defaults, performance cache, rules rule_priority/context_aware/always_include_generic, synapse repo/auto_sync/sync_interval, self_evolution analysis/insights, top-level enabled).
  - Each component that receives new config (TransclusionEngine, SummarizationEngine, RulesManager call sites, ContextDetector, SynapseManager, PatternAnalyzer, InsightEngine): assert that passed-in values match config.
- **Integration tests**:
  - Load context with max_budget and reserve_for_response set; assert effective budget respects config.
  - Rules tool: assert rule_priority and context_aware from config when tool args omitted.
  - Summarize_content: assert default target_reduction and strategy from config when args omitted.
  - Optional: TransclusionEngine cache on/off and TTL; self_evolution disabled skips analysis/insights.
- **AAA**: All tests follow Arrange-Act-Assert; no blanket skips without justification and linked ticket.
- **Pydantic v2**: For MCP/JSON responses, use Pydantic v2 BaseModel and model_validate_json/model_validate where applicable (see tests/tools/test_file_operations.py).

## Risks & Mitigation

- **Breaking existing behavior**: Defaults in config should match current hardcoded behavior so existing users see no change until they edit config. Mitigation: set default values in DEFAULT_OPTIMIZATION_CONFIG and in getters to match current code.
- **Scope creep**: Steps 5–7 touch rules, synapse, and self_evolution with multiple sub-properties. Mitigation: implement one subsection per step (e.g. rule_priority first, then context_detection), and document "reserved" for any deferred keys.

## Timeline

- Steps 1–2: 1–2 days (token budget, loading strategy).
- Steps 3–4: 1–2 days (summarization, performance cache).
- Steps 5–6: 2–3 days (rules wiring, synapse wiring).
- Steps 7–8: 1–2 days (self_evolution, top-level enabled).
- Testing and docs: 1 day throughout.

Total estimate: ~7–10 days.

## Notes

- Investigation report: `.cortex/reviews/optimization-config-investigation-2026-02-03T19-13.md`.
- For any property that is intentionally not wired (e.g. future use), add a short comment in OptimizationConfig or in docs and mark as "reserved" in the config schema/docs.
