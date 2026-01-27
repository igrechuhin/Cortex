"""
Adaptation Configuration - Phase 5.4

Configuration for learning and adaptation behavior.
"""

from typing import cast

from pydantic import BaseModel

from cortex.core.models import JsonValue, ModelDict
from cortex.refactoring.models import (
    AdaptationConfigModel,
    AdaptationSummary,
    AdaptationValidationResult,
)

_SELF_EVOLUTION_KEY_PREFIX = "self_evolution."


def _normalize_key(key: str) -> str:
    if key.startswith(_SELF_EVOLUTION_KEY_PREFIX):
        return key
    return f"{_SELF_EVOLUTION_KEY_PREFIX}{key}"


def _try_get_nested_value(
    root: JsonValue | BaseModel, keys: list[str]
) -> JsonValue | None:
    current: JsonValue | BaseModel = root
    for part in keys:
        if isinstance(current, BaseModel):
            if not hasattr(current, part):
                return None
            current = getattr(current, part)
            continue
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue
        return None
    if isinstance(current, BaseModel):
        return cast(JsonValue, cast(ModelDict, current.model_dump(mode="json")))
    return current


def _deep_set(target: dict[str, JsonValue], keys: list[str], value: JsonValue) -> None:
    if not keys:
        raise ValueError("keys cannot be empty")

    current: dict[str, JsonValue] = target
    for part in keys[:-1]:
        existing = current.get(part)
        if not isinstance(existing, dict):
            new_dict: dict[str, JsonValue] = {}
            current[part] = new_dict
            current = new_dict
        else:
            current = existing

    current[keys[-1]] = value


class AdaptationConfig:
    """
    Configuration for learning and adaptation behavior.

    Integrates with OptimizationConfig for self-evolution settings.
    """

    def __init__(self, base_config: ModelDict | None = None):
        """
        Initialize adaptation configuration.

        Args:
            base_config: Base configuration dictionary (usually from
            OptimizationConfig.config)
        """
        if base_config is None:
            self._model = AdaptationConfigModel()
            return

        raw_se = base_config.get("self_evolution")
        se_dict: dict[str, JsonValue] = raw_se if isinstance(raw_se, dict) else {}
        self._model = AdaptationConfigModel.model_validate({"self_evolution": se_dict})

    def get(self, key: str, default: JsonValue | None = None) -> JsonValue:
        """
        Get configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "learning.enabled")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        normalized = _normalize_key(key)
        keys = normalized.split(".")
        result = _try_get_nested_value(self._model, keys)
        return default if result is None else result

    def set(self, key: str, value: JsonValue) -> None:
        """
        Set configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "learning.enabled")
            value: Value to set
        """
        normalized = _normalize_key(key)
        keys = normalized.split(".")
        data = cast(dict[str, JsonValue], self._model.model_dump(mode="python"))
        _deep_set(data, keys, value)
        self._model = AdaptationConfigModel.model_validate(data)

    def is_learning_enabled(self) -> bool:
        """Check if learning is enabled."""
        return self._model.self_evolution.learning.enabled

    def get_learning_rate(self) -> str:
        """Get learning rate setting."""
        return self._model.self_evolution.learning.learning_rate

    def should_remember_rejections(self) -> bool:
        """Check if rejections should be remembered."""
        return self._model.self_evolution.learning.remember_rejections

    def should_adapt_suggestions(self) -> bool:
        """Check if suggestions should be adapted based on learning."""
        return self._model.self_evolution.learning.adapt_suggestions

    def get_min_feedback_count(self) -> int:
        """Get minimum feedback count before adapting."""
        return self._model.self_evolution.learning.min_feedback_count

    def get_confidence_adjustment_limit(self) -> float:
        """Get maximum confidence adjustment."""
        return self._model.self_evolution.learning.confidence_adjustment_limit

    def should_collect_feedback(self) -> bool:
        """Check if feedback should be collected."""
        return self._model.self_evolution.feedback.collect_feedback

    def should_prompt_for_feedback(self) -> bool:
        """Check if user should be prompted for feedback."""
        return self._model.self_evolution.feedback.prompt_for_feedback

    def get_feedback_types(self) -> list[str]:
        """Get available feedback types."""
        return self._model.self_evolution.feedback.feedback_types

    def should_allow_comments(self) -> bool:
        """Check if comments are allowed with feedback."""
        return self._model.self_evolution.feedback.allow_comments

    def is_pattern_recognition_enabled(self) -> bool:
        """Check if pattern recognition is enabled."""
        return self._model.self_evolution.pattern_recognition.enabled

    def get_min_pattern_occurrences(self) -> int:
        """Get minimum pattern occurrences."""
        return self._model.self_evolution.pattern_recognition.min_pattern_occurrences

    def get_pattern_confidence_threshold(self) -> float:
        """Get pattern confidence threshold."""
        return (
            self._model.self_evolution.pattern_recognition.pattern_confidence_threshold
        )

    def get_forget_old_patterns_days(self) -> int:
        """Get number of days before forgetting old patterns."""
        return self._model.self_evolution.pattern_recognition.forget_old_patterns_days

    def should_auto_adjust_thresholds(self) -> bool:
        """Check if thresholds should be auto-adjusted."""
        return self._model.self_evolution.adaptation.auto_adjust_thresholds

    def get_min_confidence_threshold(self) -> float:
        """Get minimum confidence threshold."""
        return self._model.self_evolution.adaptation.min_confidence_threshold

    def get_max_confidence_threshold(self) -> float:
        """Get maximum confidence threshold."""
        return self._model.self_evolution.adaptation.max_confidence_threshold

    def get_threshold_adjustment_step(self) -> float:
        """Get threshold adjustment step size."""
        return self._model.self_evolution.adaptation.threshold_adjustment_step

    def should_adapt_to_user_style(self) -> bool:
        """Check if system should adapt to user style."""
        return self._model.self_evolution.adaptation.adapt_to_user_style

    def should_filter_by_learned_patterns(self) -> bool:
        """Check if suggestions should be filtered by learned patterns."""
        return (
            self._model.self_evolution.suggestion_filtering.filter_by_learned_patterns
        )

    def should_filter_by_user_preferences(self) -> bool:
        """Check if suggestions should be filtered by user preferences."""
        return (
            self._model.self_evolution.suggestion_filtering.filter_by_user_preferences
        )

    def should_show_filtered_count(self) -> bool:
        """Check if filtered count should be shown."""
        return self._model.self_evolution.suggestion_filtering.show_filtered_count

    def should_allow_override(self) -> bool:
        """Check if users can override filtering."""
        return self._model.self_evolution.suggestion_filtering.allow_override

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

    def to_dict(self) -> ModelDict:
        """Export self_evolution configuration as JSON-serializable dict."""
        data = cast(ModelDict, self._model.model_dump(mode="json"))
        se = data.get("self_evolution")
        return cast(ModelDict, se if isinstance(se, dict) else {})

    def update(self, updates: ModelDict) -> None:
        """Update configuration with new values (expects self_evolution-shaped dict)."""
        data = cast(dict[str, JsonValue], self._model.model_dump(mode="python"))
        _deep_set(data, ["self_evolution"], updates)
        self._model = AdaptationConfigModel.model_validate(data)

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self._model = AdaptationConfigModel()

    def _validate_learning_rate(self, issues: list[str]) -> None:
        """Validate learning rate setting."""
        learning_rate = self.get_learning_rate()
        if learning_rate not in ["aggressive", "moderate", "conservative"]:
            issues.append(
                f"Invalid learning_rate: {learning_rate}. "
                + "Must be 'aggressive', 'moderate', or 'conservative'."
            )

    def _validate_confidence_thresholds(self, issues: list[str]) -> None:
        """Validate confidence threshold settings."""
        min_threshold = self.get_min_confidence_threshold()
        max_threshold = self.get_max_confidence_threshold()
        if not (0.0 <= min_threshold <= 1.0):
            issues.append(
                "min_confidence_threshold must be between 0 and 1 "
                + f"(got {min_threshold})"
            )
        if not (0.0 <= max_threshold <= 1.0):
            issues.append(
                "max_confidence_threshold must be between 0 and 1 "
                + f"(got {max_threshold})"
            )
        if min_threshold >= max_threshold:
            issues.append(
                f"min_confidence_threshold ({min_threshold}) must be less than "
                + f"max_confidence_threshold ({max_threshold})"
            )

    def _validate_feedback_and_patterns(
        self, issues: list[str], warnings: list[str]
    ) -> None:
        """Validate feedback and pattern settings."""
        min_feedback = self.get_min_feedback_count()
        if min_feedback < 1:
            issues.append(f"min_feedback_count must be at least 1 (got {min_feedback})")

        adjustment_limit = self.get_confidence_adjustment_limit()
        if not (0.0 <= adjustment_limit <= 1.0):
            warnings.append(
                f"confidence_adjustment_limit is {adjustment_limit}. "
                + "Recommended range is 0.1-0.3."
            )

        min_occurrences = self.get_min_pattern_occurrences()
        if min_occurrences < 1:
            issues.append(
                f"min_pattern_occurrences must be at least 1 (got {min_occurrences})"
            )

        pattern_threshold = self.get_pattern_confidence_threshold()
        if not (0.0 <= pattern_threshold <= 1.0):
            issues.append(
                "pattern_confidence_threshold must be between 0 and 1 "
                + f"(got {pattern_threshold})"
            )

    def _validate_learning_flags(self, warnings: list[str]) -> None:
        """Validate learning feature flags."""
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

    def validate(self) -> AdaptationValidationResult:
        """Validate current configuration and return structured result."""
        issues: list[str] = []
        warnings: list[str] = []

        self._validate_learning_rate(issues)
        self._validate_confidence_thresholds(issues)
        self._validate_feedback_and_patterns(issues, warnings)
        self._validate_learning_flags(warnings)

        return AdaptationValidationResult(
            valid=not issues, issues=issues, warnings=warnings
        )

    def get_summary(self) -> AdaptationSummary:
        """Get a typed summary of current configuration."""
        return AdaptationSummary(
            learning_enabled=self.is_learning_enabled(),
            learning_rate=self.get_learning_rate(),
            min_confidence_threshold=self.get_min_confidence_threshold(),
            max_confidence_threshold=self.get_max_confidence_threshold(),
            pattern_recognition_enabled=self.is_pattern_recognition_enabled(),
            feedback_collection_enabled=self.should_collect_feedback(),
            auto_adjust_thresholds=self.should_auto_adjust_thresholds(),
            adapt_to_user_style=self.should_adapt_to_user_style(),
            filter_by_learned_patterns=self.should_filter_by_learned_patterns(),
            filter_by_user_preferences=self.should_filter_by_user_preferences(),
        )
