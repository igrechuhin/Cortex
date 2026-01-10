"""
Configuration management for token optimization features.

This module provides functionality to manage optimization settings
through a JSON configuration file.
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file

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
        # Shared rules configuration (NEW in Phase 6)
        "shared_rules_enabled": False,
        "shared_rules_folder": ".shared-rules",
        "shared_rules_repo": "",
        "auto_sync_shared_rules": True,
        "sync_interval_minutes": 60,
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
        self.config_path: Path = self.project_root / ".memory-bank-optimization.json"
        self.config: dict[str, object] = self._load_config()

    def _load_config(self) -> dict[str, object]:
        """
        Load configuration from file or create default.

        Returns:
            Configuration dictionary

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    user_config_raw = cast(object, json.load(f))
                    if not isinstance(user_config_raw, dict):
                        return cast(dict[str, object], DEFAULT_OPTIMIZATION_CONFIG)
                    user_config: dict[str, object] = cast(
                        dict[str, object], user_config_raw
                    )

                # Merge with defaults
                return self.merge_configs(
                    cast(dict[str, object], DEFAULT_OPTIMIZATION_CONFIG),
                    user_config,
                )

            except (OSError, json.JSONDecodeError) as e:
                print(f"Warning: Failed to load optimization config: {e}")
                return cast(dict[str, object], deepcopy(DEFAULT_OPTIMIZATION_CONFIG))

        return cast(dict[str, object], deepcopy(DEFAULT_OPTIMIZATION_CONFIG))

    def merge_configs(
        self, default: dict[str, object], user: dict[str, object]
    ) -> dict[str, object]:
        """
        Recursively merge user config with defaults.

        Args:
            default: Default configuration
            user: User configuration

        Returns:
            Merged configuration
        """
        # Use deepcopy to avoid sharing references with DEFAULT_OPTIMIZATION_CONFIG
        result = deepcopy(default)

        for key, value in user.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self.merge_configs(
                    cast(dict[str, object], result[key]), cast(dict[str, object], value)
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
            async with open_async_text_file(self.config_path, "w", "utf-8") as f:
                _ = await f.write(json.dumps(self.config, indent=2))
            return True

        except OSError as e:
            print(f"Error: Failed to save optimization config: {e}")
            return False

    def get(self, key_path: str, default: object = None) -> object:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path (e.g., "token_budget.default_budget")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key_path.split(".")
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: object) -> bool:
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

        # Navigate to parent
        current: dict[str, object] = self.config
        for key in keys[:-1]:
            if key not in current:
                # Create new dict entry
                new_dict: dict[str, object] = {}
                current[key] = new_dict
                current = new_dict
            else:
                # Check if existing value is a dict
                next_value = current[key]
                if not isinstance(next_value, dict):
                    return False
                current = cast(dict[str, object], next_value)

        # Set value - current is guaranteed to be a dict here
        current[keys[-1]] = value
        return True

    async def reset(self) -> None:
        """Reset configuration to defaults."""
        # Delete config file if it exists to ensure clean reset
        if self.config_path.exists():
            self.config_path.unlink()
        # Reset to defaults directly (ensures clean state)
        self.config = cast(dict[str, object], deepcopy(DEFAULT_OPTIMIZATION_CONFIG))
        _ = await self.save_config()

    def get_token_budget(self) -> int:
        """Get default token budget."""
        return cast(int, self.get("token_budget.default_budget", 80000))

    def get_max_token_budget(self) -> int:
        """Get maximum token budget."""
        return cast(int, self.get("token_budget.max_budget", 100000))

    def get_loading_strategy(self) -> str:
        """Get default loading strategy."""
        return cast(str, self.get("loading_strategy.default", "dependency_aware"))

    def get_mandatory_files(self) -> list[str]:
        """Get list of mandatory files."""
        return cast(
            list[str],
            self.get("loading_strategy.mandatory_files", ["memorybankinstructions.md"]),
        )

    def get_priority_order(self) -> list[str]:
        """Get file priority order."""
        return cast(
            list[str],
            self.get(
                "loading_strategy.priority_order",
                [
                    "memorybankinstructions.md",
                    "projectBrief.md",
                    "activeContext.md",
                    "systemPatterns.md",
                    "techContext.md",
                    "productContext.md",
                    "progress.md",
                ],
            ),
        )

    def is_summarization_enabled(self) -> bool:
        """Check if summarization is enabled."""
        return cast(bool, self.get("summarization.enabled", True))

    def get_summarization_strategy(self) -> str:
        """Get summarization strategy."""
        return cast(str, self.get("summarization.strategy", "extract_key_sections"))

    def get_summarization_target_reduction(self) -> float:
        """Get target reduction for summarization."""
        return cast(float, self.get("summarization.target_reduction", 0.5))

    def get_relevance_weights(self) -> dict[str, float]:
        """
        Get relevance scoring weights.

        Returns:
            Dict with keyword_weight, dependency_weight, recency_weight, quality_weight
        """
        return {
            "keyword_weight": cast(float, self.get("relevance.keyword_weight", 0.4)),
            "dependency_weight": cast(
                float, self.get("relevance.dependency_weight", 0.3)
            ),
            "recency_weight": cast(float, self.get("relevance.recency_weight", 0.2)),
            "quality_weight": cast(float, self.get("relevance.quality_weight", 0.1)),
        }

    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return cast(bool, self.get("performance.cache_enabled", True))

    def get_cache_ttl(self) -> int:
        """Get cache TTL in seconds."""
        return cast(int, self.get("performance.cache_ttl_seconds", 3600))

    def is_rules_enabled(self) -> bool:
        """Check if rules indexing is enabled."""
        return cast(bool, self.get("rules.enabled", False))

    def get_rules_folder(self) -> str | None:
        """Get rules folder path."""
        return cast(str | None, self.get("rules.rules_folder", ".cursorrules"))

    def get_rules_reindex_interval(self) -> int:
        """Get rules reindex interval in minutes."""
        return cast(int, self.get("rules.reindex_interval_minutes", 30))

    def is_rules_auto_include(self) -> bool:
        """Check if rules should be auto-included in context."""
        return cast(bool, self.get("rules.auto_include_in_context", True))

    def get_rules_max_tokens(self) -> int:
        """Get maximum tokens for rules."""
        return cast(int, self.get("rules.max_rules_tokens", 5000))

    def get_rules_min_relevance(self) -> float:
        """Get minimum relevance score for rules."""
        return cast(float, self.get("rules.min_relevance_score", 0.3))

    def is_self_evolution_enabled(self) -> bool:
        """Check if self-evolution is enabled."""
        return cast(bool, self.get("self_evolution.enabled", True))

    def is_usage_tracking_enabled(self) -> bool:
        """Check if usage pattern tracking is enabled."""
        return cast(
            bool, self.get("self_evolution.analysis.track_usage_patterns", True)
        )

    def get_pattern_window_days(self) -> int:
        """Get pattern analysis window in days."""
        return cast(int, self.get("self_evolution.analysis.pattern_window_days", 30))

    def get_min_access_count(self) -> int:
        """Get minimum access count for pattern analysis."""
        return cast(int, self.get("self_evolution.analysis.min_access_count", 5))

    def is_task_tracking_enabled(self) -> bool:
        """Check if task pattern tracking is enabled."""
        return cast(bool, self.get("self_evolution.analysis.track_task_patterns", True))

    def is_auto_insights_enabled(self) -> bool:
        """Check if insights should be auto-generated."""
        return cast(bool, self.get("self_evolution.insights.auto_generate", False))

    def get_min_impact_score(self) -> float:
        """Get minimum impact score for insights."""
        return cast(float, self.get("self_evolution.insights.min_impact_score", 0.5))

    def get_insight_categories(self) -> list[str]:
        """Get insight categories to analyze."""
        return cast(
            list[str],
            self.get(
                "self_evolution.insights.categories",
                ["usage", "organization", "redundancy", "dependencies", "quality"],
            ),
        )

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate current configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check token budgets
        default_budget = self.get("token_budget.default_budget")
        max_budget = self.get("token_budget.max_budget")

        if not isinstance(default_budget, int) or default_budget <= 0:
            return False, "token_budget.default_budget must be a positive integer"

        if not isinstance(max_budget, int) or max_budget <= 0:
            return False, "token_budget.max_budget must be a positive integer"

        if default_budget > max_budget:
            return False, "token_budget.default_budget cannot exceed max_budget"

        # Check loading strategy
        strategy = self.get("loading_strategy.default")
        valid_strategies = ["priority", "dependency_aware", "section_level", "hybrid"]

        if strategy not in valid_strategies:
            return (
                False,
                f"loading_strategy.default must be one of: {', '.join(valid_strategies)}",
            )

        # Check summarization
        target_reduction = self.get("summarization.target_reduction")

        if (
            not isinstance(target_reduction, (int, float))
            or not 0 < target_reduction < 1
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

    def to_dict(self) -> dict[str, object]:
        """
        Get configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        return self.config.copy()

    def __repr__(self) -> str:
        """String representation."""
        return f"OptimizationConfig(project_root={self.project_root!r})"
