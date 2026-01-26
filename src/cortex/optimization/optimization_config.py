"""
Configuration management for token optimization features.

This module provides functionality to manage optimization settings
through a JSON configuration file.
"""

import copy
import json
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.models import JsonValue, ModelDict
from cortex.optimization.models import OptimizationConfigModel

DEFAULT_OPTIMIZATION_CONFIG = {
    "enabled": True,
    "token_budget": {
        "default_budget": 80000,
        "max_budget": 100000,
        "reserve_for_response": 10000,
    },
    "loading_strategy": {
        "default": "dependency_aware",
        "mandatory_files": ["memorybankinstructions.md"],
        "priority_order": [
            "memorybankinstructions.md",
            "projectBrief.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
            "progress.md",
        ],
    },
    "summarization": {
        "enabled": True,
        "auto_summarize_old_files": False,
        "age_threshold_days": 90,
        "target_reduction": 0.5,
        "strategy": "extract_key_sections",
        "cache_summaries": True,
    },
    "relevance": {
        "keyword_weight": 0.4,
        "dependency_weight": 0.3,
        "recency_weight": 0.2,
        "quality_weight": 0.1,
    },
    "performance": {
        "cache_enabled": True,
        "cache_ttl_seconds": 3600,
        "max_cache_size_mb": 50,
    },
    "rules": {
        "enabled": False,
        "rules_folder": ".cursorrules",
        "reindex_interval_minutes": 30,
        "auto_include_in_context": True,
        "max_rules_tokens": 5000,
        "min_relevance_score": 0.3,
        "rule_priority": "local_overrides_shared",  # or "shared_overrides_local"
        "context_aware_loading": True,
        "always_include_generic": True,
        "context_detection": {
            "enabled": True,
            "detect_from_task": True,
            "detect_from_files": True,
            "language_keywords": {
                "python": ["python", "django", "flask", "fastapi", "pytest", "py"],
                "swift": ["swift", "swiftui", "ios", "uikit", "combine", "cocoa"],
                "javascript": [
                    "javascript",
                    "js",
                    "react",
                    "vue",
                    "node",
                    "typescript",
                    "ts",
                ],
                "rust": ["rust", "cargo", "rustc"],
                "go": ["golang", "go"],
                "java": ["java", "spring", "maven", "gradle"],
                "csharp": ["c#", "csharp", "dotnet", ".net"],
                "cpp": ["c++", "cpp", "cmake"],
            },
        },
    },
    "synapse": {
        "enabled": False,
        "synapse_folder": ".cortex/synapse",
        "synapse_repo": "",
        "auto_sync": True,
        "sync_interval_minutes": 60,
    },
    "self_evolution": {
        "enabled": True,
        "analysis": {
            "track_usage_patterns": True,
            "pattern_window_days": 30,
            "min_access_count": 5,
            "track_task_patterns": True,
        },
        "insights": {
            "auto_generate": False,
            "min_impact_score": 0.5,
            "categories": [
                "usage",
                "organization",
                "redundancy",
                "dependencies",
                "quality",
            ],
        },
    },
}


class OptimizationConfig:
    """Manage optimization configuration."""

    def __init__(self, project_root: Path):
        """
        Initialize optimization configuration.

        Args:
            project_root: Project root directory
        """
        self.project_root: Path = Path(project_root)
        self.config_path: Path = self.project_root / ".cortex" / "optimization.json"
        self.config: ModelDict = self._load_config()

    def _load_config(self) -> ModelDict:
        """
        Load configuration from file or create default.

        Returns:
            Dictionary with configuration values

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        default_config = cast(ModelDict, copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG))

        # Early return if config file doesn't exist - use defaults
        if not self.config_path.exists():
            return default_config

        try:
            with open(self.config_path) as f:
                user_config_raw = cast(object, json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to load optimization config: {e}")
            return default_config

        # Validate config type and parse with Pydantic
        if not isinstance(user_config_raw, dict):
            return default_config

        # Merge raw config with defaults (validation is handled by validate())
        return self.merge_configs(
            default_config,
            cast(ModelDict, user_config_raw),
        )

    def merge_configs(self, default: ModelDict, user: ModelDict) -> ModelDict:
        """
        Recursively merge user config dict with defaults.

        Args:
            default: Default configuration dict
            user: User configuration dict

        Returns:
            Merged configuration dict

        Note: This method works with ModelDict for flexibility during config
        loading, but the result is validated into OptimizationConfigModel.
        """
        result = default.copy()

        for key, value in user.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self.merge_configs(
                    cast(ModelDict, result[key]),
                    cast(ModelDict, value),
                )
            else:
                result[key] = value

        return result

    async def save_config(self) -> bool:
        """
        Save current configuration to file.

        Returns:
            True if saved successfully
        """
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            async with open_async_text_file(self.config_path, "w", "utf-8") as f:
                _ = await f.write(json.dumps(self.config, indent=2))
            return True

        except OSError as e:
            from cortex.core.logging_config import logger

            logger.error(f"Failed to save optimization config: {e}")
            return False

    def get(self, key_path: str, default: JsonValue | None = None) -> JsonValue:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path (e.g., "token_budget.default_budget")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key_path.split(".")
        value: JsonValue = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: JsonValue) -> bool:
        """
        Set configuration value using dot notation.

        Args:
            key_path: Dot-separated path (e.g., "token_budget.default_budget")
            value: Value to set

        Returns:
            True if set successfully
        """
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

        # Set value
        current[keys[-1]] = value
        return True

    async def reset(self) -> None:
        """Reset configuration to defaults."""
        # Delete config file if it exists to ensure clean reset
        if self.config_path.exists():
            self.config_path.unlink()
        self.config = cast(ModelDict, copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG))
        _ = await self.save_config()

    def get_token_budget(self) -> int:
        """Get default token budget."""
        value = self.get("token_budget.default_budget", 80000)
        return int(value) if isinstance(value, int) else 80000

    def get_max_token_budget(self) -> int:
        """Get maximum token budget."""
        value = self.get("token_budget.max_budget", 100000)
        return int(value) if isinstance(value, int) else 100000

    def get_loading_strategy(self) -> str:
        """Get default loading strategy."""
        value = self.get("loading_strategy.default", "dependency_aware")
        return str(value) if isinstance(value, str) else "dependency_aware"

    def get_mandatory_files(self) -> list[str]:
        """Get list of mandatory files."""
        value = self.get("loading_strategy.mandatory_files", [])
        if not isinstance(value, list):
            return []
        items = cast(list[JsonValue], value)
        return [str(item) for item in items if isinstance(item, str)]

    def get_priority_order(self) -> list[str]:
        """Get file priority order."""
        value = self.get("loading_strategy.priority_order", [])
        if not isinstance(value, list):
            return []
        items = cast(list[JsonValue], value)
        return [str(item) for item in items if isinstance(item, str)]

    def is_summarization_enabled(self) -> bool:
        """Check if summarization is enabled."""
        value = self.get("summarization.enabled", True)
        return bool(value) if isinstance(value, bool) else True

    def get_summarization_strategy(self) -> str:
        """Get summarization strategy."""
        value = self.get("summarization.strategy", "extract_key_sections")
        return str(value) if isinstance(value, str) else "extract_key_sections"

    def get_summarization_target_reduction(self) -> float:
        """Get target reduction for summarization."""
        value = self.get("summarization.target_reduction", 0.5)
        return float(value) if isinstance(value, (int, float)) else 0.5

    def get_relevance_weights(self) -> dict[str, float]:
        """
        Get relevance scoring weights.

        Returns:
            Dict with keyword_weight, dependency_weight, recency_weight, quality_weight
        """
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
        """Check if caching is enabled."""
        value = self.get("performance.cache_enabled", True)
        return bool(value) if isinstance(value, bool) else True

    def get_cache_ttl(self) -> int:
        """Get cache TTL in seconds."""
        value = self.get("performance.cache_ttl_seconds", 3600)
        return int(value) if isinstance(value, int) else 3600

    def is_rules_enabled(self) -> bool:
        """Check if rules indexing is enabled."""
        value = self.get("rules.enabled", False)
        return bool(value) if isinstance(value, bool) else False

    def get_rules_folder(self) -> str | None:
        """Get rules folder path."""
        value = self.get("rules.rules_folder", None)
        return str(value) if isinstance(value, str) else None

    def get_rules_reindex_interval(self) -> int:
        """Get rules reindex interval in minutes."""
        value = self.get("rules.reindex_interval_minutes", 30)
        return int(value) if isinstance(value, int) else 30

    def is_rules_auto_include(self) -> bool:
        """Check if rules should be auto-included in context."""
        value = self.get("rules.auto_include_in_context", True)
        return bool(value) if isinstance(value, bool) else True

    def get_rules_max_tokens(self) -> int:
        """Get maximum tokens for rules."""
        value = self.get("rules.max_rules_tokens", 5000)
        return int(value) if isinstance(value, int) else 5000

    def get_rules_min_relevance(self) -> float:
        """Get minimum relevance score for rules."""
        value = self.get("rules.min_relevance_score", 0.3)
        return float(value) if isinstance(value, (int, float)) else 0.3

    def is_synapse_enabled(self) -> bool:
        """Check if Synapse is enabled."""
        value = self.get("synapse.enabled", False)
        return bool(value) if isinstance(value, bool) else False

    def get_synapse_folder(self) -> str:
        """Get Synapse folder path."""
        value = self.get("synapse.synapse_folder", ".cortex/synapse")
        return str(value) if isinstance(value, str) else ".cortex/synapse"

    def get_synapse_repo(self) -> str:
        """Get Synapse repository URL."""
        value = self.get("synapse.synapse_repo", "")
        return str(value) if isinstance(value, str) else ""

    def is_synapse_auto_sync(self) -> bool:
        """Check if Synapse auto-sync is enabled."""
        value = self.get("synapse.auto_sync", True)
        return bool(value) if isinstance(value, bool) else True

    def get_synapse_sync_interval(self) -> int:
        """Get Synapse sync interval in minutes."""
        value = self.get("synapse.sync_interval_minutes", 60)
        return int(value) if isinstance(value, int) else 60

    def is_self_evolution_enabled(self) -> bool:
        """Check if self-evolution is enabled."""
        value = self.get("self_evolution.enabled", True)
        return bool(value) if isinstance(value, bool) else True

    def is_usage_tracking_enabled(self) -> bool:
        """Check if usage pattern tracking is enabled."""
        value = self.get("self_evolution.analysis.track_usage_patterns", True)
        return bool(value) if isinstance(value, bool) else True

    def get_pattern_window_days(self) -> int:
        """Get pattern analysis window in days."""
        value = self.get("self_evolution.analysis.pattern_window_days", 30)
        return int(value) if isinstance(value, int) else 30

    def get_min_access_count(self) -> int:
        """Get minimum access count for pattern analysis."""
        value = self.get("self_evolution.analysis.min_access_count", 5)
        return int(value) if isinstance(value, int) else 5

    def is_task_tracking_enabled(self) -> bool:
        """Check if task pattern tracking is enabled."""
        value = self.get("self_evolution.analysis.track_task_patterns", True)
        return bool(value) if isinstance(value, bool) else True

    def is_auto_insights_enabled(self) -> bool:
        """Check if insights should be auto-generated."""
        value = self.get("self_evolution.insights.auto_generate", False)
        return bool(value) if isinstance(value, bool) else False

    def get_min_impact_score(self) -> float:
        """Get minimum impact score for insights."""
        value = self.get("self_evolution.insights.min_impact_score", 0.5)
        return float(value) if isinstance(value, (int, float)) else 0.5

    def get_insight_categories(self) -> list[str]:
        """Get insight categories to analyze."""
        value = self.get(
            "self_evolution.insights.categories",
            [
                "usage",
                "organization",
                "redundancy",
                "dependencies",
                "quality",
            ],
        )
        if not isinstance(value, list):
            return []
        items = cast(list[JsonValue], value)
        return [str(item) for item in items if isinstance(item, str)]

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate current configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        default_budget = self.get("token_budget.default_budget")
        max_budget = self.get("token_budget.max_budget")

        if not isinstance(default_budget, int) or default_budget <= 0:
            return False, "token_budget.default_budget must be a positive integer"
        if not isinstance(max_budget, int) or max_budget <= 0:
            return False, "token_budget.max_budget must be a positive integer"
        if default_budget > max_budget:
            return False, "token_budget.default_budget cannot exceed max_budget"

        strategy = self.get("loading_strategy.default", "dependency_aware")
        valid_strategies = ["priority", "dependency_aware", "section_level", "hybrid"]

        if not isinstance(strategy, str) or strategy not in valid_strategies:
            return (
                False,
                f"loading_strategy.default must be one of: {', '.join(valid_strategies)}",
            )

        # Check summarization
        target_reduction = self.get("summarization.target_reduction", 0.5)
        if (
            not isinstance(target_reduction, (int, float))
            or not 0 < float(target_reduction) < 1
        ):
            return (
                False,
                "summarization.target_reduction must be between 0 and 1",
            )

        # Check relevance weights
        weights = self.get_relevance_weights()
        total_weight = sum(weights.values())

        if not 0.9 <= total_weight <= 1.1:
            return False, f"relevance weights must sum to ~1.0 (got {total_weight})"

        return True, None

    def to_dict(self) -> ModelDict:
        """Return a defensive copy of current config."""
        return copy.deepcopy(self.config)

    def to_model(self) -> OptimizationConfigModel:
        """Return validated config model (strict, raises on invalid config)."""
        default_config = cast(ModelDict, copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG))
        merged = self.merge_configs(default_config, self.config)
        return OptimizationConfigModel.model_validate(merged)

    def __repr__(self) -> str:
        """String representation."""
        return f"OptimizationConfig(project_root={self.project_root!r})"
