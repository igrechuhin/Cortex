"""
Adaptation Configuration - Phase 5.4

Configuration for learning and adaptation behavior.
"""

from __future__ import annotations

from typing import TypeGuard, cast


def _is_str_dict(value: object) -> TypeGuard[dict[str, object]]:
    """Type guard to check if value is a dict[str, object]."""
    return isinstance(value, dict)


class AdaptationConfig:
    """
    Configuration for learning and adaptation behavior.

    Integrates with OptimizationConfig for self-evolution settings.
    """

    def __init__(self, base_config: dict[str, object] | None = None):
        """
        Initialize adaptation configuration.

        Args:
            base_config: Base configuration dictionary
                (usually from optimization_config)
        """
        self.config: dict[str, object] = base_config or {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Initialize default configuration values."""
        se_config = self._ensure_self_evolution_config()
        self._init_learning_defaults(se_config)
        self._init_feedback_defaults(se_config)
        self._init_pattern_recognition_defaults(se_config)
        self._init_adaptation_defaults(se_config)
        self._init_suggestion_filtering_defaults(se_config)

    def get(self, key: str, default: object = None) -> object:
        """
        Get configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "learning.enabled")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys: list[str] = key.split(".")
        value: object = self.config

        for k in keys:
            if _is_str_dict(value):
                if k in value:
                    value = value[k]
                else:
                    return default
            else:
                return default

        return value

    def set(self, key: str, value: object) -> None:
        """
        Set configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "learning.enabled")
            value: Value to set
        """
        keys: list[str] = key.split(".")
        config: dict[str, object] = self.config

        # Navigate to the parent dict
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = cast(dict[str, object], config[k])

        # Set the value
        config[keys[-1]] = value

    def is_learning_enabled(self) -> bool:
        """Check if learning is enabled."""
        return cast(bool, self.get("self_evolution.learning.enabled", True))

    def get_learning_rate(self) -> str:
        """Get learning rate setting."""
        return cast(
            str, self.get("self_evolution.learning.learning_rate", "conservative")
        )

    def should_remember_rejections(self) -> bool:
        """Check if rejections should be remembered."""
        return cast(bool, self.get("self_evolution.learning.remember_rejections", True))

    def should_adapt_suggestions(self) -> bool:
        """Check if suggestions should be adapted based on learning."""
        return cast(bool, self.get("self_evolution.learning.adapt_suggestions", True))

    def get_min_feedback_count(self) -> int:
        """Get minimum feedback count before adapting."""
        return cast(int, self.get("self_evolution.learning.min_feedback_count", 5))

    def get_confidence_adjustment_limit(self) -> float:
        """Get maximum confidence adjustment."""
        return cast(
            float, self.get("self_evolution.learning.confidence_adjustment_limit", 0.2)
        )

    def should_collect_feedback(self) -> bool:
        """Check if feedback should be collected."""
        return cast(bool, self.get("self_evolution.feedback.collect_feedback", True))

    def should_prompt_for_feedback(self) -> bool:
        """Check if user should be prompted for feedback."""
        return cast(
            bool, self.get("self_evolution.feedback.prompt_for_feedback", False)
        )

    def get_feedback_types(self) -> list[str]:
        """Get available feedback types."""
        result: object = self.get(
            "self_evolution.feedback.feedback_types",
            ["helpful", "not_helpful", "incorrect"],
        )
        return cast(list[str], result)

    def should_allow_comments(self) -> bool:
        """Check if comments are allowed with feedback."""
        return cast(bool, self.get("self_evolution.feedback.allow_comments", True))

    def is_pattern_recognition_enabled(self) -> bool:
        """Check if pattern recognition is enabled."""
        return cast(bool, self.get("self_evolution.pattern_recognition.enabled", True))

    def get_min_pattern_occurrences(self) -> int:
        """Get minimum pattern occurrences."""
        return cast(
            int,
            self.get("self_evolution.pattern_recognition.min_pattern_occurrences", 3),
        )

    def get_pattern_confidence_threshold(self) -> float:
        """Get pattern confidence threshold."""
        return cast(
            float,
            self.get(
                "self_evolution.pattern_recognition.pattern_confidence_threshold", 0.7
            ),
        )

    def get_forget_old_patterns_days(self) -> int:
        """Get number of days before forgetting old patterns."""
        return cast(
            int,
            self.get("self_evolution.pattern_recognition.forget_old_patterns_days", 90),
        )

    def should_auto_adjust_thresholds(self) -> bool:
        """Check if thresholds should be auto-adjusted."""
        return cast(
            bool, self.get("self_evolution.adaptation.auto_adjust_thresholds", True)
        )

    def get_min_confidence_threshold(self) -> float:
        """Get minimum confidence threshold."""
        return cast(
            float, self.get("self_evolution.adaptation.min_confidence_threshold", 0.5)
        )

    def get_max_confidence_threshold(self) -> float:
        """Get maximum confidence threshold."""
        return cast(
            float, self.get("self_evolution.adaptation.max_confidence_threshold", 0.9)
        )

    def get_threshold_adjustment_step(self) -> float:
        """Get threshold adjustment step size."""
        return cast(
            float, self.get("self_evolution.adaptation.threshold_adjustment_step", 0.05)
        )

    def should_adapt_to_user_style(self) -> bool:
        """Check if system should adapt to user style."""
        return cast(
            bool, self.get("self_evolution.adaptation.adapt_to_user_style", True)
        )

    def should_filter_by_learned_patterns(self) -> bool:
        """Check if suggestions should be filtered by learned patterns."""
        return cast(
            bool,
            self.get(
                "self_evolution.suggestion_filtering.filter_by_learned_patterns", True
            ),
        )

    def should_filter_by_user_preferences(self) -> bool:
        """Check if suggestions should be filtered by user preferences."""
        return cast(
            bool,
            self.get(
                "self_evolution.suggestion_filtering.filter_by_user_preferences", True
            ),
        )

    def should_show_filtered_count(self) -> bool:
        """Check if filtered count should be shown."""
        return cast(
            bool,
            self.get("self_evolution.suggestion_filtering.show_filtered_count", True),
        )

    def should_allow_override(self) -> bool:
        """Check if users can override filtering."""
        return cast(
            bool, self.get("self_evolution.suggestion_filtering.allow_override", True)
        )

    def get_learning_rate_multiplier(self) -> float:
        """
        Get learning rate multiplier based on learning rate setting.

        Returns:
            Multiplier for learning adjustments (0.5-2.0)
        """
        rate = self.get_learning_rate()

        if rate == "aggressive":
            return 2.0
        elif rate == "moderate":
            return 1.0
        elif rate == "conservative":
            return 0.5
        else:
            return 1.0

    def to_dict(self) -> dict[str, object]:
        """Export configuration as dictionary."""
        result: object = self.config.get("self_evolution", {})
        return cast(dict[str, object], result)

    def update(self, updates: dict[str, object]) -> None:
        """
        Update configuration with new values.

        Args:
            updates: Dictionary of updates
        """
        if "self_evolution" not in self.config:
            self.config["self_evolution"] = {}

        se_config: dict[str, object] = cast(
            dict[str, object], self.config["self_evolution"]
        )
        self._deep_update(se_config, updates)

    def _deep_update(
        self, target: dict[str, object], updates: dict[str, object]
    ) -> None:
        """
        Deep update dictionary.

        Args:
            target: Target dictionary to update
            updates: Updates to apply
        """
        for key, value in updates.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                target_dict: dict[str, object] = cast(dict[str, object], target[key])
                updates_dict: dict[str, object] = cast(dict[str, object], value)
                self._deep_update(target_dict, updates_dict)
            else:
                target[key] = value

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        if "self_evolution" in self.config:
            del self.config["self_evolution"]
        self._init_defaults()

    def validate(self) -> dict[str, object]:
        """
        Validate configuration.

        Returns:
            Validation results with any issues
        """
        issues: list[str] = []
        warnings: list[str] = []

        self._validate_learning_rate(issues)
        self._validate_thresholds(issues)
        self._validate_feedback_count(issues)
        self._validate_adjustment_limit(warnings)
        self._validate_pattern_settings(issues)
        self._validate_learning_status(warnings)

        return cast(
            dict[str, object],
            {
                "valid": len(issues) == 0,
                "issues": issues,
                "warnings": warnings,
            },
        )

    def _validate_learning_rate(self, issues: list[str]) -> None:
        """Validate learning rate setting.

        Args:
            issues: List to append validation issues to
        """
        learning_rate = self.get_learning_rate()
        if learning_rate not in ["aggressive", "moderate", "conservative"]:
            issues.append(
                f"Invalid learning_rate: {learning_rate}. "
                + "Must be 'aggressive', 'moderate', or 'conservative'."
            )

    def _validate_thresholds(self, issues: list[str]) -> None:
        """Validate confidence thresholds.

        Args:
            issues: List to append validation issues to
        """
        min_threshold = self.get_min_confidence_threshold()
        max_threshold = self.get_max_confidence_threshold()

        if min_threshold < 0 or min_threshold > 1:
            issues.append(
                "min_confidence_threshold must be between 0 and 1 "
                + f"(got {min_threshold})"
            )

        if max_threshold < 0 or max_threshold > 1:
            issues.append(
                "max_confidence_threshold must be between 0 and 1 "
                + f"(got {max_threshold})"
            )

        if min_threshold >= max_threshold:
            issues.append(
                f"min_confidence_threshold ({min_threshold}) must be less than "
                + f"max_confidence_threshold ({max_threshold})"
            )

    def _validate_feedback_count(self, issues: list[str]) -> None:
        """Validate feedback count settings.

        Args:
            issues: List to append validation issues to
        """
        min_feedback = self.get_min_feedback_count()
        if min_feedback < 1:
            issues.append(f"min_feedback_count must be at least 1 (got {min_feedback})")

    def _validate_adjustment_limit(self, warnings: list[str]) -> None:
        """Validate confidence adjustment limit.

        Args:
            warnings: List to append validation warnings to
        """
        adjustment_limit = self.get_confidence_adjustment_limit()
        if adjustment_limit < 0 or adjustment_limit > 1:
            warnings.append(
                f"confidence_adjustment_limit is {adjustment_limit}. "
                + "Recommended range is 0.1-0.3."
            )

    def _validate_pattern_settings(self, issues: list[str]) -> None:
        """Validate pattern recognition settings.

        Args:
            issues: List to append validation issues to
        """
        min_occurrences = self.get_min_pattern_occurrences()
        if min_occurrences < 1:
            issues.append(
                f"min_pattern_occurrences must be at least 1 (got {min_occurrences})"
            )

        pattern_threshold = self.get_pattern_confidence_threshold()
        if pattern_threshold < 0 or pattern_threshold > 1:
            issues.append(
                "pattern_confidence_threshold must be between 0 and 1 "
                + f"(got {pattern_threshold})"
            )

    def _validate_learning_status(self, warnings: list[str]) -> None:
        """Validate learning status and generate warnings.

        Args:
            warnings: List to append validation warnings to
        """
        if not self.is_learning_enabled():
            warnings.append(
                "Learning is disabled. The system will not adapt to user feedback."
            )

        if not self.should_adapt_suggestions():
            warnings.append(
                "Suggestion adaptation is disabled. "
                + "The system will collect feedback but not use it to "
                + "improve suggestions."
            )

    def get_summary(self) -> dict[str, object]:
        """
        Get configuration summary.

        Returns:
            Summary of current configuration
        """
        return cast(
            dict[str, object],
            {
                "learning_enabled": self.is_learning_enabled(),
                "learning_rate": self.get_learning_rate(),
                "min_confidence_threshold": self.get_min_confidence_threshold(),
                "max_confidence_threshold": self.get_max_confidence_threshold(),
                "pattern_recognition_enabled": self.is_pattern_recognition_enabled(),
                "feedback_collection_enabled": self.should_collect_feedback(),
                "auto_adjust_thresholds": self.should_auto_adjust_thresholds(),
                "adapt_to_user_style": self.should_adapt_to_user_style(),
                "filter_by_learned_patterns": self.should_filter_by_learned_patterns(),
                "filter_by_user_preferences": self.should_filter_by_user_preferences(),
            },
        )

    def _ensure_self_evolution_config(self) -> dict[str, object]:
        """Ensure self_evolution config section exists."""
        if "self_evolution" not in self.config:
            self.config["self_evolution"] = {}
        return cast(dict[str, object], self.config["self_evolution"])

    def _init_learning_defaults(self, se_config: dict[str, object]) -> None:
        """Initialize learning configuration defaults."""
        if "learning" not in se_config:
            se_config["learning"] = {
                "enabled": True,
                "learning_rate": "conservative",
                "remember_rejections": True,
                "adapt_suggestions": True,
                "export_patterns": False,
                "min_feedback_count": 5,
                "confidence_adjustment_limit": 0.2,
            }

    def _init_feedback_defaults(self, se_config: dict[str, object]) -> None:
        """Initialize feedback collection defaults."""
        if "feedback" not in se_config:
            se_config["feedback"] = {
                "collect_feedback": True,
                "prompt_for_feedback": False,
                "feedback_types": ["helpful", "not_helpful", "incorrect"],
                "allow_comments": True,
            }

    def _init_pattern_recognition_defaults(self, se_config: dict[str, object]) -> None:
        """Initialize pattern recognition defaults."""
        if "pattern_recognition" not in se_config:
            se_config["pattern_recognition"] = {
                "enabled": True,
                "min_pattern_occurrences": 3,
                "pattern_confidence_threshold": 0.7,
                "forget_old_patterns_days": 90,
            }

    def _init_adaptation_defaults(self, se_config: dict[str, object]) -> None:
        """Initialize adaptation behavior defaults."""
        if "adaptation" not in se_config:
            se_config["adaptation"] = {
                "auto_adjust_thresholds": True,
                "min_confidence_threshold": 0.5,
                "max_confidence_threshold": 0.9,
                "threshold_adjustment_step": 0.05,
                "adapt_to_user_style": True,
            }

    def _init_suggestion_filtering_defaults(self, se_config: dict[str, object]) -> None:
        """Initialize suggestion filtering defaults."""
        if "suggestion_filtering" not in se_config:
            se_config["suggestion_filtering"] = {
                "filter_by_learned_patterns": True,
                "filter_by_user_preferences": True,
                "show_filtered_count": True,
                "allow_override": True,
            }
