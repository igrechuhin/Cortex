# Configuration Reference

This document is the **generated reference** of all configuration defaults used by Cortex. Defaults are extracted from Pydantic config models and default dicts in source. For usage and examples, see [Configuration Guide](../guides/configuration.md).

## Source of truth

| Config file | Source | Model / constant |
|-------------|--------|-------------------|
| `.cortex/config/validation.json` | `cortex.validation.models` | `ValidationConfigModel` |
| `.cortex/config/optimization.json` | `cortex.optimization.config` | `DEFAULT_OPTIMIZATION_CONFIG` + `OptimizationConfigModel` |
| `.cortex/config/structure.json` | `cortex.structure.structure_config` | `DEFAULT_STRUCTURE`; schema: `cortex.structure.models.StructureConfigModel` |

To regenerate default values from source, run from project root:

```bash
uv run python .cortex/synapse/scripts/python/generate_config_reference.py
```

This writes `docs/api/config-defaults.json` with current defaults for validation, optimization, and structure. The tables below are the authoritative reference; the JSON file is for tooling and diffing.

---

## Validation configuration (`.cortex/config/validation.json`)

Loaded by `ValidationConfig`; validated with `ValidationConfigModel`.

### Validation: top-level

| Name | Type | Default | Valid range / values | Description |
|------|------|---------|----------------------|-------------|
| `enabled` | boolean | `true` | — | Whether validation is enabled |
| `auto_validate_on_write` | boolean | `true` | — | Whether to auto-validate on write |
| `strict_mode` | boolean | `false` | — | Whether to use strict validation mode |
| `token_budget` | object | (see below) | — | Token budget configuration |
| `duplication` | object | (see below) | — | Duplication detection configuration |
| `schemas` | object | (see below) | — | Schema validation configuration |
| `quality` | object | (see below) | — | Quality metrics configuration |

### Validation: token_budget

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `max_total_tokens` | int | `100000` | ≥ 1 | Maximum total tokens allowed |
| `warn_at_percentage` | float | `80.0` | 0–100 | Warning threshold percentage |
| `per_file_max` | int | `15000` | ≥ 1 | Maximum tokens per file |
| `per_file_warn` | int | `12000` | ≥ 1 | Warning threshold per file |

### Validation: duplication

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `enabled` | boolean | `true` | — | Whether duplication detection is enabled |
| `threshold` | float | `0.85` | 0.0–1.0 | Similarity threshold for duplicate detection |
| `min_length` | int | `50` | ≥ 0 | Minimum section length in characters |
| `suggest_transclusion` | boolean | `true` | — | Whether to suggest transclusion for duplicates |

### Validation: schemas

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `enforce_required_sections` | boolean | `true` | — | Whether to enforce required sections |
| `enforce_section_order` | boolean | `false` | — | Whether to enforce section order |
| `custom_schemas` | object | `{}` | — | Custom schema definitions by file name |

### Validation: quality

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `minimum_score` | float | `70.0` | 0–100 | Minimum acceptable quality score |
| `fail_below` | float | `50.0` | 0–100 | Score below which validation fails |
| `weights` | object | (see below) | — | Quality score weights (must sum to 1.0) |

#### Validation: quality.weights

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `completeness` | float | `0.25` | 0.0–1.0 | Weight for completeness |
| `consistency` | float | `0.25` | 0.0–1.0 | Weight for consistency |
| `freshness` | float | `0.15` | 0.0–1.0 | Weight for freshness |
| `structure` | float | `0.20` | 0.0–1.0 | Weight for structure |
| `token_efficiency` | float | `0.15` | 0.0–1.0 | Weight for token efficiency |

---

## Optimization configuration (`.cortex/config/optimization.json`)

Loaded by `OptimizationConfig`; merged with `DEFAULT_OPTIMIZATION_CONFIG`; validated with `OptimizationConfigModel`.

### Optimization: top-level

| Name | Type | Default | Valid range / values | Description |
|------|------|---------|----------------------|-------------|
| `enabled` | boolean | `true` | — | Whether optimization is enabled |
| `token_budget` | object | (see below) | — | Token budget configuration |
| `loading_strategy` | object | (see below) | — | Loading strategy configuration |
| `summarization` | object | (see below) | — | Summarization configuration |
| `relevance` | object | (see below) | — | Relevance scoring weights |
| `performance` | object | (see below) | — | Performance and caching |
| `rules` | object | (see below) | — | Rules indexing and loading |
| `synapse` | object | (see below) | — | Synapse shared rules |
| `self_evolution` | object | (see below) | — | Self-evolution and adaptive learning |
| `tool_search` | object | (see below) | — | Tool search / deferred loading (Phase 49) |

### Optimization: token_budget

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `default_budget` | int | `80000` | ≥ 1 | Default token budget for operations |
| `max_budget` | int | `100000` | ≥ 1 | Maximum token budget |
| `reserve_for_response` | int | `10000` | ≥ 0 | Tokens reserved for response |

### Optimization: loading_strategy

| Name | Type | Default | Valid values | Description |
|------|------|---------|---------------|-------------|
| `default` | string | `"dependency_aware"` | `priority`, `dependency_aware`, `section_level`, `hybrid` | Default loading strategy |
| `mandatory_files` | list[string] | `["memorybankinstructions.md"]` | — | Files that must always be loaded |
| `priority_order` | list[string] | (memory bank file order) | — | File loading priority order |
| `always_load_sections` | object | `{"projectBrief.md": [], "activeContext.md": ["## Current Focus", "## Next Steps"]}` | — | Sections always loaded in full when depth=metadata_only |

### Optimization: summarization

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `enabled` | boolean | `true` | — | Whether summarization is enabled |
| `auto_summarize_old_files` | boolean | `false` | — | Auto-summarize files older than threshold |
| `age_threshold_days` | int | `90` | ≥ 1 | Age threshold for auto-summarization (days) |
| `target_reduction` | float | `0.5` | 0–1 (exclusive) | Target reduction ratio |
| `strategy` | string | `"extract_key_sections"` | `extract_key_sections`, `compress_examples`, `remove_verbose`, `hybrid` | Summarization strategy |
| `cache_summaries` | boolean | `true` | — | Whether to cache generated summaries |

### Optimization: relevance

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `keyword_weight` | float | `0.4` | 0.0–1.0 | Weight for keyword matching |
| `dependency_weight` | float | `0.3` | 0.0–1.0 | Weight for dependency relevance |
| `recency_weight` | float | `0.2` | 0.0–1.0 | Weight for recent modifications |
| `quality_weight` | float | `0.1` | 0.0–1.0 | Weight for quality score |

(Weights should sum to ~1.0.)

### Optimization: performance

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `cache_enabled` | boolean | `true` | — | Whether caching is enabled |
| `cache_ttl_seconds` | int | `3600` | ≥ 0 | Cache TTL in seconds |
| `max_cache_size_mb` | int | `50` | ≥ 1 | Maximum cache size in MB |

### Optimization: rules

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `enabled` | boolean | `false` | — | Whether rules indexing is enabled |
| `rules_folder` | string | `".cortex/rules"` | — | Path to rules folder |
| `reindex_interval_minutes` | int | `30` | ≥ 1 | Rules reindex interval (minutes) |
| `auto_include_in_context` | boolean | `true` | — | Auto-include relevant rules in context |
| `max_rules_tokens` | int | `5000` | ≥ 0 | Maximum tokens for rules |
| `min_relevance_score` | float | `0.3` | 0.0–1.0 | Minimum relevance score for rules |
| `rule_priority` | string | `"local_overrides_shared"` | `local_overrides_shared`, `shared_overrides_local` | Rule priority strategy |
| `context_aware_loading` | boolean | `true` | — | Use context-aware rule loading |
| `always_include_generic` | boolean | `true` | — | Always include generic rules |
| `context_detection` | object | (see below) | — | Context detection settings |

#### Optimization: rules.context_detection

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `enabled` | boolean | `true` | Whether context detection is enabled |
| `detect_from_task` | boolean | `true` | Detect context from task description |
| `detect_from_files` | boolean | `true` | Detect context from project files |
| `language_keywords` | object | (per-language lists) | Language detection keywords (python, swift, javascript, rust, go, java, csharp, cpp) |

### Optimization: synapse

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `enabled` | boolean | `false` | — | Whether Synapse is enabled |
| `synapse_folder` | string | `".cortex/synapse"` | — | Path to Synapse folder |
| `synapse_repo` | string | `""` | — | Synapse repository URL |
| `auto_sync` | boolean | `true` | — | Auto-sync with Synapse repo |
| `sync_interval_minutes` | int | `60` | ≥ 1 | Sync interval in minutes |

### self_evolution

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `enabled` | boolean | `true` | Whether self-evolution is enabled |
| `analysis` | object | (see below) | Analysis configuration |
| `insights` | object | (see below) | Insights configuration |

#### Optimization: self_evolution.analysis

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `track_usage_patterns` | boolean | `true` | — | Track file usage patterns |
| `pattern_window_days` | int | `30` | ≥ 1 | Days to analyze for patterns |
| `min_access_count` | int | `5` | ≥ 1 | Minimum accesses for pattern detection |
| `track_task_patterns` | boolean | `true` | — | Track task-related patterns |

#### Optimization: self_evolution.insights

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `auto_generate` | boolean | `false` | — | Auto-generate optimization insights |
| `min_impact_score` | float | `0.5` | 0.0–1.0 | Minimum impact score for insights |
| `categories` | list[string] | `["usage", "organization", "redundancy", "dependencies", "quality"]` | — | Insight categories to analyze |

### Optimization: tool_search

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `enabled` | boolean | `false` | Whether deferred tool loading / tool search is enabled |
| `always_loaded` | list[string] | `[]` | Tool names to load initially when tool search is enabled |
| `deferred_medium` | list[string] | `[]` | Deferred tool names (medium priority) |
| `deferred_low` | list[string] | `[]` | Deferred tool names (low priority) |

---

## Structure configuration (`.cortex/config/structure.json`)

Loaded by `StructureConfig`; defaults from `DEFAULT_STRUCTURE`; schema in `StructureConfigModel`.

### Structure: version

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `version` | string | `"2.0"` | Configuration version |

### Structure: layout

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `root` | string | `".cortex"` | Root directory name |
| `memory_bank` | string | `"memory-bank"` | Memory bank directory |
| `rules` | string | `"rules"` | Rules directory |
| `plans` | string | `"plans"` | Plans directory |
| `config` | string | `"config"` | Config directory |
| `archived` | string | `"archived"` | Archived directory |
| `reviews` | string | `"reviews"` | Reviews directory |

### Structure: housekeeping

| Name | Type | Default | Valid range | Description |
|------|------|---------|-------------|-------------|
| `auto_cleanup` | boolean | `true` | — | Enable auto cleanup |
| `stale_plan_days` | int | `90` | ≥ 1 | Days before plan is considered stale |
| `archive_completed_plans` | boolean | `true` | — | Archive completed plans |
| `detect_duplicates` | boolean | `true` | — | Detect duplicates |

### Structure: rules

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `use_submodule` | boolean | `false` | Use git submodule for rules |
| `submodule_path` | string | `"rules/shared"` | Path for shared rules submodule |
| `local_rules_path` | string | `"rules/local"` | Path for local rules |
| `shared_repo_url` | string \| null | `null` | URL for shared rules repository |

---

## Environment and transport

Not stored in JSON; read from environment at runtime.

### Transport (MCP)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CORTEX_MCP_TRANSPORT` | string | (derived) | `stdio` when port unset; `sse` when port set. Explicit override. |
| `CORTEX_MCP_PORT` | int \| null | unset | Port for SSE/HTTP transport |
| `CORTEX_MCP_HOST` | string | `"127.0.0.1"` | Host for SSE/HTTP |

Valid transports: `stdio`, `sse`, `streamable-http`.

### MCP stability (constants)

Defined in `cortex.core.constants` and `cortex.core.mcp_stability_config`; not user-configurable via JSON.

| Constant | Default | Description |
|----------|---------|-------------|
| `MCP_MAX_CONCURRENT_TOOLS` | `5` | Maximum concurrent MCP tool executions |
| `MCP_MAX_CONCURRENT_RESOURCES` | `10` | Maximum concurrent resource reads |
| `MCP_CONNECTION_RETRY_ATTEMPTS` | `3` | Max attempts (initial + retries) for connection retries |
| `MCP_CONNECTION_RETRY_DELAY_SECONDS` | `2` | Base delay in seconds between retries |
| `LONG_RUNNING_SEMAPHORE_WAIT_SECONDS` | `330.0` | Max seconds to wait for long-running semaphore |
| `LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS` | `330.0` | Max seconds a long-running tool may hold the semaphore (allows one full Step 12 run) |

---

## Regenerating defaults

From the project root:

```bash
uv run python .cortex/synapse/scripts/python/generate_config_reference.py
```

The script writes `docs/api/config-defaults.json` from `ValidationConfigModel()`, `DEFAULT_OPTIMIZATION_CONFIG` (with `tool_search` injected), and `DEFAULT_STRUCTURE`. Run it after changing any config model or `DEFAULT_*` in source to keep the generated defaults in sync.

## See also

- [Configuration Guide](../guides/configuration.md) — usage, examples, and best practices
- [API Tools](tools.md) — configuration MCP tools (`configure_validation`, `configure_optimization`, etc.)
- [Architecture](../architecture.md) — system design and config loading
