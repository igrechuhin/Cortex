"""
Configuration management for token optimization features.

This module provides functionality to manage optimization settings
through a JSON configuration file. Defaults, loading, and validation
are split into config_defaults, config_loading, and config_validation.
"""

import copy
from pathlib import Path
from typing import cast

from cortex.core.constants import MemoryBankFile
from cortex.core.models import JsonValue, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.optimization.config_defaults import DEFAULT_OPTIMIZATION_CONFIG
from cortex.optimization.config_loading import (
    get_default_config_with_tool_search,
    save_config_async,
)
from cortex.optimization.config_loading import (
    load_config as load_config_from_path,
)
from cortex.optimization.config_loading import (
    merge_configs as merge_configs_impl,
)
from cortex.optimization.config_validation import validate_optimization_config
from cortex.optimization.models import OptimizationConfigModel

__all__ = ["DEFAULT_OPTIMIZATION_CONFIG", "OptimizationConfig"]


class OptimizationConfig:
    """Manage optimization configuration."""

    def __init__(self, project_root: Path) -> None:
        self.project_root: Path = Path(project_root)
        config_dir = get_cortex_path(self.project_root, CortexResourceType.CONFIG)
        self.config_path: Path = config_dir / "optimization.json"
        self.config: ModelDict = load_config_from_path(self.config_path)

    def merge_configs(self, default: ModelDict, user: ModelDict) -> ModelDict:
        """Recursively merge user config dict with defaults."""
        return merge_configs_impl(default, user)

    async def save_config(self) -> bool:
        """Save current configuration to file. Returns True if saved successfully."""
        return await save_config_async(self.config_path, self.config)

    def get(self, key_path: str, default: JsonValue | None = None) -> JsonValue:
        """Get configuration value using dot notation."""
        keys = key_path.split(".")
        value: JsonValue = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, key_path: str, value: JsonValue) -> bool:
        """Set configuration value using dot notation."""
        keys = key_path.split(".")
        if not keys:
            return False
        current: ModelDict = self.config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            if not isinstance(current[key], dict):
                return False
            current = cast(ModelDict, current[key])
        current[keys[-1]] = value
        return True

    async def reset(self) -> None:
        """Reset configuration to defaults."""
        if self.config_path.exists():
            self.config_path.unlink()
        self.config = get_default_config_with_tool_search()
        _ = await self.save_config()

    def get_tool_search_config(self) -> ModelDict:
        """Get tool search config; falls back to build_category_config() if missing."""
        raw = self.config.get("tool_search")
        if isinstance(raw, dict):
            return cast(ModelDict, raw)
        from cortex.tools.structure.categories import build_category_config

        return cast(ModelDict, build_category_config().model_dump())

    def get_token_budget(self) -> int:
        value = self.get("token_budget.default_budget", 25000)
        return int(value) if isinstance(value, int) else 25000

    def get_max_token_budget(self) -> int:
        value = self.get("token_budget.max_budget", 100000)
        return int(value) if isinstance(value, int) else 100000

    def get_reserve_for_response(self) -> int:
        value = self.get("token_budget.reserve_for_response", 10000)
        return int(value) if isinstance(value, int) else 10000

    def get_max_response_tokens(self) -> int:
        value = self.get("max_response_tokens", 50000)
        return int(value) if isinstance(value, int) and value > 0 else 50000

    def get_loading_strategy(self) -> str:
        value = self.get("loading_strategy.default", "dependency_aware")
        return str(value) if isinstance(value, str) else "dependency_aware"

    def get_mandatory_files(self) -> list[str]:
        value = self.get("loading_strategy.mandatory_files", [])
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, str)]

    def get_priority_order(self) -> list[str]:
        value = self.get("loading_strategy.priority_order", [])
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, str)]

    def get_always_load_sections(self) -> dict[str, list[str]]:
        value = self.get(
            "loading_strategy.always_load_sections",
            {
                MemoryBankFile.PROJECT_BRIEF: [],
                MemoryBankFile.ACTIVE_CONTEXT: ["## Current Focus", "## Next Steps"],
            },
        )
        if not isinstance(value, dict):
            return {
                MemoryBankFile.PROJECT_BRIEF: [],
                MemoryBankFile.ACTIVE_CONTEXT: ["## Current Focus", "## Next Steps"],
            }
        result: dict[str, list[str]] = {}
        for file_name, sections_raw in value.items():
            if isinstance(sections_raw, list):
                result[str(file_name)] = [
                    str(s) for s in sections_raw if isinstance(s, str)
                ]
            else:
                result[str(file_name)] = []
        return result

    def is_summarization_enabled(self) -> bool:
        value = self.get("summarization.enabled", True)
        return bool(value) if isinstance(value, bool) else True

    def get_summarization_strategy(self) -> str:
        value = self.get("summarization.strategy", "extract_key_sections")
        return str(value) if isinstance(value, str) else "extract_key_sections"

    def get_summarization_target_reduction(self) -> float:
        value = self.get("summarization.target_reduction", 0.5)
        return float(value) if isinstance(value, (int, float)) else 0.5

    def is_summarization_cache_enabled(self) -> bool:
        value = self.get("summarization.cache_summaries", True)
        return bool(value) if isinstance(value, bool) else True

    def get_summarization_age_threshold_days(self) -> int:
        value = self.get("summarization.age_threshold_days", 90)
        return int(value) if isinstance(value, int) else 90

    def is_summarization_auto_summarize_old_files(self) -> bool:
        value = self.get("summarization.auto_summarize_old_files", False)
        return bool(value) if isinstance(value, bool) else False

    def get_relevance_weights(self) -> dict[str, float]:
        keyword = self.get("relevance.keyword_weight", 0.4)
        dep = self.get("relevance.dependency_weight", 0.3)
        rec = self.get("relevance.recency_weight", 0.2)
        qual = self.get("relevance.quality_weight", 0.1)
        return {
            "keyword_weight": (
                float(keyword) if isinstance(keyword, (int, float)) else 0.4
            ),
            "dependency_weight": float(dep) if isinstance(dep, (int, float)) else 0.3,
            "recency_weight": float(rec) if isinstance(rec, (int, float)) else 0.2,
            "quality_weight": float(qual) if isinstance(qual, (int, float)) else 0.1,
        }

    def is_cache_enabled(self) -> bool:
        value = self.get("performance.cache_enabled", True)
        return bool(value) if isinstance(value, bool) else True

    def get_cache_ttl(self) -> int:
        value = self.get("performance.cache_ttl_seconds", 3600)
        return int(value) if isinstance(value, int) else 3600

    def get_max_cache_size_mb(self) -> int:
        value = self.get("performance.max_cache_size_mb", 50)
        return int(value) if isinstance(value, int) else 50

    def is_rules_enabled(self) -> bool:
        value = self.get("rules.enabled", False)
        return bool(value) if isinstance(value, bool) else False

    def get_rules_folder(self) -> str | None:
        value = self.get("rules.rules_folder", None)
        return str(value) if isinstance(value, str) else None

    def get_rules_reindex_interval(self) -> int:
        value = self.get("rules.reindex_interval_minutes", 30)
        return int(value) if isinstance(value, int) else 30

    def is_rules_auto_include(self) -> bool:
        value = self.get("rules.auto_include_in_context", True)
        return bool(value) if isinstance(value, bool) else True

    def get_rules_max_tokens(self) -> int:
        value = self.get("rules.max_rules_tokens", 5000)
        return int(value) if isinstance(value, int) else 5000

    def get_rules_min_relevance(self) -> float:
        value = self.get("rules.min_relevance_score", 0.3)
        return float(value) if isinstance(value, (int, float)) else 0.3

    def get_rule_priority(self) -> str:
        value = self.get("rules.rule_priority", "local_overrides_shared")
        return str(value) if isinstance(value, str) else "local_overrides_shared"

    def is_context_aware_loading(self) -> bool:
        value = self.get("rules.context_aware_loading", True)
        return bool(value) if isinstance(value, bool) else True

    def is_always_include_generic(self) -> bool:
        value = self.get("rules.always_include_generic", True)
        return bool(value) if isinstance(value, bool) else True

    def get_language_keywords(self) -> dict[str, list[str]]:
        value = self.get("rules.context_detection.language_keywords", {})
        if not isinstance(value, dict):
            return {}
        return {
            str(lang): [str(kw) for kw in keywords if isinstance(kw, str)]
            for lang, keywords in value.items()
            if isinstance(keywords, list)
        }

    def is_synapse_enabled(self) -> bool:
        value = self.get("synapse.enabled", False)
        return bool(value) if isinstance(value, bool) else False

    def get_synapse_folder(self) -> str:
        default = f".cortex/{CortexResourceType.SYNAPSE.value}"
        value = self.get("synapse.synapse_folder", default)
        return str(value) if isinstance(value, str) else default

    def get_synapse_repo(self) -> str:
        value = self.get("synapse.synapse_repo", "")
        return str(value) if isinstance(value, str) else ""

    def is_synapse_auto_sync(self) -> bool:
        value = self.get("synapse.auto_sync", True)
        return bool(value) if isinstance(value, bool) else True

    def get_synapse_sync_interval(self) -> int:
        value = self.get("synapse.sync_interval_minutes", 60)
        return int(value) if isinstance(value, int) else 60

    def is_self_evolution_enabled(self) -> bool:
        value = self.get("self_evolution.enabled", True)
        return bool(value) if isinstance(value, bool) else True

    def is_usage_tracking_enabled(self) -> bool:
        value = self.get("self_evolution.analysis.track_usage_patterns", True)
        return bool(value) if isinstance(value, bool) else True

    def get_pattern_window_days(self) -> int:
        value = self.get("self_evolution.analysis.pattern_window_days", 30)
        return int(value) if isinstance(value, int) else 30

    def get_min_access_count(self) -> int:
        value = self.get("self_evolution.analysis.min_access_count", 5)
        return int(value) if isinstance(value, int) else 5

    def is_task_tracking_enabled(self) -> bool:
        value = self.get("self_evolution.analysis.track_task_patterns", True)
        return bool(value) if isinstance(value, bool) else True

    def is_auto_insights_enabled(self) -> bool:
        value = self.get("self_evolution.insights.auto_generate", False)
        return bool(value) if isinstance(value, bool) else False

    def get_min_impact_score(self) -> float:
        value = self.get("self_evolution.insights.min_impact_score", 0.5)
        return float(value) if isinstance(value, (int, float)) else 0.5

    def get_insight_categories(self) -> list[str]:
        value = self.get(
            "self_evolution.insights.categories",
            ["usage", "organization", "redundancy", "dependencies", "quality"],
        )
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, str)]

    def is_optimization_enabled(self) -> bool:
        value = self.get("enabled", True)
        return bool(value) if isinstance(value, bool) else True

    def validate(self) -> tuple[bool, str | None]:
        """Validate current configuration. Returns (is_valid, error_message)."""
        return validate_optimization_config(self.config)

    def to_dict(self) -> ModelDict:
        """Return a defensive copy of current config."""
        return copy.deepcopy(self.config)

    def to_model(self) -> OptimizationConfigModel:
        """Return validated config model (strict, raises on invalid config)."""
        default = get_default_config_with_tool_search()
        merged = self.merge_configs(default, self.config)
        return OptimizationConfigModel.model_validate(merged)

    def __repr__(self) -> str:
        return f"OptimizationConfig(project_root={self.project_root!r})"
