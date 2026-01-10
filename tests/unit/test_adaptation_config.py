"""Unit tests for AdaptationConfig - Phase 5.4"""

from typing import cast

from cortex.refactoring.adaptation_config import AdaptationConfig


class TestAdaptationConfigInitialization:
    """Test AdaptationConfig initialization."""

    def test_initialization_with_no_config(self):
        """Test initialization with default config."""
        # Arrange & Act
        config = AdaptationConfig()

        # Assert
        assert config.config is not None
        assert "self_evolution" in config.config

    def test_initialization_with_base_config(self):
        """Test initialization with base configuration."""
        # Arrange
        base: dict[str, object] = {"existing_key": "value"}

        # Act
        config = AdaptationConfig(base_config=base)

        # Assert
        assert config.config["existing_key"] == "value"
        assert "self_evolution" in config.config

    def test_initialization_creates_default_sections(self):
        """Test initialization creates all default sections."""
        # Arrange & Act
        config = AdaptationConfig()

        # Assert
        se_config = config.config.get("self_evolution")
        assert isinstance(se_config, dict)
        assert "learning" in se_config
        assert "feedback" in se_config
        assert "pattern_recognition" in se_config
        assert "adaptation" in se_config
        assert "suggestion_filtering" in se_config


class TestGetConfiguration:
    """Test getting configuration values."""

    def test_get_with_dot_notation(self):
        """Test getting value with dot notation."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get("self_evolution.learning.enabled")

        # Assert
        assert result is True

    def test_get_with_default_value(self):
        """Test getting missing value returns default."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get("nonexistent.key", default="default_value")

        # Assert
        assert result == "default_value"

    def test_get_nested_value(self):
        """Test getting nested configuration value."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get("self_evolution.learning.learning_rate")

        # Assert
        assert result == "conservative"


class TestSetConfiguration:
    """Test setting configuration values."""

    def test_set_with_dot_notation(self):
        """Test setting value with dot notation."""
        # Arrange
        config = AdaptationConfig()

        # Act
        config.set("self_evolution.learning.enabled", False)

        # Assert
        assert config.get("self_evolution.learning.enabled") is False

    def test_set_creates_nested_structure(self):
        """Test setting creates nested dictionary structure."""
        # Arrange
        config = AdaptationConfig()

        # Act
        config.set("new.nested.key", "value")

        # Assert
        assert config.get("new.nested.key") == "value"

    def test_set_overwrites_existing_value(self):
        """Test setting overwrites existing value."""
        # Arrange
        config = AdaptationConfig()
        original = config.get("self_evolution.learning.learning_rate")

        # Act
        config.set("self_evolution.learning.learning_rate", "aggressive")

        # Assert
        new_value = config.get("self_evolution.learning.learning_rate")
        assert new_value != original
        assert new_value == "aggressive"


class TestLearningConfiguration:
    """Test learning-related configuration methods."""

    def test_is_learning_enabled(self):
        """Test checking if learning is enabled."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.is_learning_enabled()

        # Assert
        assert result is True

    def test_get_learning_rate(self):
        """Test getting learning rate."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_learning_rate()

        # Assert
        assert result == "conservative"

    def test_should_remember_rejections(self):
        """Test checking if rejections should be remembered."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_remember_rejections()

        # Assert
        assert result is True

    def test_should_adapt_suggestions(self):
        """Test checking if suggestions should be adapted."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_adapt_suggestions()

        # Assert
        assert result is True

    def test_get_min_feedback_count(self):
        """Test getting minimum feedback count."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_min_feedback_count()

        # Assert
        assert result == 5

    def test_get_confidence_adjustment_limit(self):
        """Test getting confidence adjustment limit."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_confidence_adjustment_limit()

        # Assert
        assert result == 0.2


class TestFeedbackConfiguration:
    """Test feedback-related configuration methods."""

    def test_should_collect_feedback(self):
        """Test checking if feedback should be collected."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_collect_feedback()

        # Assert
        assert result is True

    def test_should_prompt_for_feedback(self):
        """Test checking if user should be prompted for feedback."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_prompt_for_feedback()

        # Assert
        assert result is False

    def test_get_feedback_types(self):
        """Test getting available feedback types."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_feedback_types()

        # Assert
        assert isinstance(result, list)
        assert "helpful" in result
        assert "not_helpful" in result

    def test_should_allow_comments(self):
        """Test checking if comments are allowed."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_allow_comments()

        # Assert
        assert result is True


class TestPatternRecognitionConfiguration:
    """Test pattern recognition configuration methods."""

    def test_is_pattern_recognition_enabled(self):
        """Test checking if pattern recognition is enabled."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.is_pattern_recognition_enabled()

        # Assert
        assert result is True

    def test_get_min_pattern_occurrences(self):
        """Test getting minimum pattern occurrences."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_min_pattern_occurrences()

        # Assert
        assert result == 3

    def test_get_pattern_confidence_threshold(self):
        """Test getting pattern confidence threshold."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_pattern_confidence_threshold()

        # Assert
        assert result == 0.7

    def test_get_forget_old_patterns_days(self):
        """Test getting days before forgetting old patterns."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_forget_old_patterns_days()

        # Assert
        assert result == 90


class TestAdaptationConfiguration:
    """Test adaptation behavior configuration methods."""

    def test_should_auto_adjust_thresholds(self):
        """Test checking if thresholds should be auto-adjusted."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_auto_adjust_thresholds()

        # Assert
        assert result is True

    def test_get_min_confidence_threshold(self):
        """Test getting minimum confidence threshold."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_min_confidence_threshold()

        # Assert
        assert result == 0.5

    def test_get_max_confidence_threshold(self):
        """Test getting maximum confidence threshold."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_max_confidence_threshold()

        # Assert
        assert result == 0.9

    def test_get_threshold_adjustment_step(self):
        """Test getting threshold adjustment step."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_threshold_adjustment_step()

        # Assert
        assert result == 0.05

    def test_should_adapt_to_user_style(self):
        """Test checking if system should adapt to user style."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_adapt_to_user_style()

        # Assert
        assert result is True


class TestSuggestionFilteringConfiguration:
    """Test suggestion filtering configuration methods."""

    def test_should_filter_by_learned_patterns(self):
        """Test checking if filtering by learned patterns is enabled."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_filter_by_learned_patterns()

        # Assert
        assert result is True

    def test_should_filter_by_user_preferences(self):
        """Test checking if filtering by user preferences is enabled."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_filter_by_user_preferences()

        # Assert
        assert result is True

    def test_should_show_filtered_count(self):
        """Test checking if filtered count should be shown."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_show_filtered_count()

        # Assert
        assert result is True

    def test_should_allow_override(self):
        """Test checking if users can override filtering."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.should_allow_override()

        # Assert
        assert result is True


class TestLearningRateMultiplier:
    """Test learning rate multiplier calculation."""

    def test_get_multiplier_for_aggressive(self):
        """Test multiplier for aggressive learning rate."""
        # Arrange
        config = AdaptationConfig()
        config.set("self_evolution.learning.learning_rate", "aggressive")

        # Act
        result = config.get_learning_rate_multiplier()

        # Assert
        assert result == 2.0

    def test_get_multiplier_for_moderate(self):
        """Test multiplier for moderate learning rate."""
        # Arrange
        config = AdaptationConfig()
        config.set("self_evolution.learning.learning_rate", "moderate")

        # Act
        result = config.get_learning_rate_multiplier()

        # Assert
        assert result == 1.0

    def test_get_multiplier_for_conservative(self):
        """Test multiplier for conservative learning rate."""
        # Arrange
        config = AdaptationConfig()
        config.set("self_evolution.learning.learning_rate", "conservative")

        # Act
        result = config.get_learning_rate_multiplier()

        # Assert
        assert result == 0.5

    def test_get_multiplier_for_unknown_defaults_to_moderate(self):
        """Test multiplier defaults to moderate for unknown rate."""
        # Arrange
        config = AdaptationConfig()
        config.set("self_evolution.learning.learning_rate", "unknown")

        # Act
        result = config.get_learning_rate_multiplier()

        # Assert
        assert result == 1.0


class TestConfigurationManagement:
    """Test configuration management methods."""

    def test_to_dict_returns_self_evolution_config(self):
        """Test to_dict returns self_evolution configuration."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert "learning" in result
        assert "feedback" in result

    def test_update_merges_configuration(self):
        """Test update merges new configuration."""
        # Arrange
        config = AdaptationConfig()
        updates: dict[str, object] = {"learning": {"enabled": False}}

        # Act
        config.update(updates)

        # Assert
        assert config.is_learning_enabled() is False

    def test_reset_to_defaults_restores_defaults(self):
        """Test reset restores default configuration."""
        # Arrange
        config = AdaptationConfig()
        config.set("self_evolution.learning.enabled", False)

        # Act
        config.reset_to_defaults()

        # Assert
        assert config.is_learning_enabled() is True


class TestValidation:
    """Test configuration validation."""

    def test_validate_with_valid_config(self):
        """Test validation passes for valid config."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.validate()

        # Assert
        assert result["valid"] is True
        issues = cast(list[str], result["issues"])
        assert len(issues) == 0

    def test_validate_detects_invalid_learning_rate(self):
        """Test validation detects invalid learning rate."""
        # Arrange
        config = AdaptationConfig()
        config.set("self_evolution.learning.learning_rate", "invalid")

        # Act
        result = config.validate()

        # Assert
        assert result["valid"] is False
        issues = cast(list[str], result["issues"])
        assert any("learning_rate" in issue for issue in issues)

    def test_validate_detects_invalid_thresholds(self):
        """Test validation detects invalid threshold values."""
        # Arrange
        config = AdaptationConfig()
        config.set("self_evolution.adaptation.min_confidence_threshold", 1.5)

        # Act
        result = config.validate()

        # Assert
        assert result["valid"] is False
        issues = cast(list[str], result["issues"])
        assert any("min_confidence_threshold" in issue for issue in issues)

    def test_validate_detects_threshold_order_issue(self):
        """Test validation detects min >= max threshold."""
        # Arrange
        config = AdaptationConfig()
        config.set("self_evolution.adaptation.min_confidence_threshold", 0.9)
        config.set("self_evolution.adaptation.max_confidence_threshold", 0.5)

        # Act
        result = config.validate()

        # Assert
        assert result["valid"] is False
        issues = cast(list[str], result["issues"])
        assert any("must be less than" in issue for issue in issues)

    def test_validate_includes_warnings(self):
        """Test validation includes warnings for suboptimal config."""
        # Arrange
        config = AdaptationConfig()
        config.set("self_evolution.learning.enabled", False)

        # Act
        result = config.validate()

        # Assert
        warnings = cast(list[str], result["warnings"])
        assert len(warnings) > 0
        assert any("disabled" in warning.lower() for warning in warnings)


class TestGetSummary:
    """Test configuration summary."""

    def test_get_summary_includes_key_settings(self):
        """Test summary includes key configuration settings."""
        # Arrange
        config = AdaptationConfig()

        # Act
        result = config.get_summary()

        # Assert
        assert "learning_enabled" in result
        assert "learning_rate" in result
        assert "min_confidence_threshold" in result
        assert "pattern_recognition_enabled" in result
        assert "feedback_collection_enabled" in result
