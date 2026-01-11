"""
Unit tests for ValidationConfig module.

Tests configuration management including:
- Config loading from files and defaults
- Config merging (user config overrides defaults)
- Dot notation access for nested values
- Config saving and persistence
- Config validation with error detection
- Helper methods for common config queries
"""

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.validation.validation_config import (
    DEFAULT_CONFIG,
    ValidationConfig,
)


@pytest.mark.unit
class TestValidationConfigInitialization:
    """Tests for ValidationConfig initialization."""

    @pytest.mark.asyncio
    async def test_initialization_with_no_config_file(self, tmp_path: Path) -> None:
        """Test initialization uses defaults when no config file exists."""
        config = ValidationConfig(project_root=tmp_path)

        assert config.project_root == tmp_path
        assert config.config_path == tmp_path / ".cortex/validation.json"
        assert config.config is not None
        assert config.config["enabled"] == DEFAULT_CONFIG["enabled"]

    @pytest.mark.asyncio
    async def test_initialization_with_existing_config(self, tmp_path: Path) -> None:
        """Test initialization loads user config from file."""
        # Create custom config
        config_path = tmp_path / ".cortex/validation.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        custom_config = {"enabled": False, "strict_mode": True}
        with open(config_path, "w") as f:
            json.dump(custom_config, f)

        config = ValidationConfig(project_root=tmp_path)

        # Custom values override defaults
        assert config.config["enabled"] is False
        assert config.config["strict_mode"] is True
        # Default values are preserved
        assert "token_budget" in config.config

    @pytest.mark.asyncio
    async def test_initialization_with_invalid_json(self, tmp_path: Path) -> None:
        """Test initialization handles invalid JSON gracefully."""
        # Create invalid JSON file
        config_path = tmp_path / ".cortex/validation.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            _ = f.write("{invalid json")

        config = ValidationConfig(project_root=tmp_path)

        # Should fall back to defaults
        assert config.config == DEFAULT_CONFIG


class TestConfigMerging:
    """Tests for merge_configs method."""

    def test_merge_flat_configs(self, tmp_path: Path) -> None:
        """Test merging flat configuration dictionaries."""
        config = ValidationConfig(project_root=tmp_path)

        default: dict[str, object] = {"a": 1, "b": 2, "c": 3}
        user: dict[str, object] = {"b": 20, "d": 4}

        merged = config.merge_configs(default, user)

        assert merged["a"] == 1  # Preserved from default
        assert merged["b"] == 20  # Override from user
        assert merged["c"] == 3  # Preserved from default
        assert merged["d"] == 4  # Added from user

    def test_merge_nested_configs(self, tmp_path: Path) -> None:
        """Test merging nested configuration dictionaries."""
        config = ValidationConfig(project_root=tmp_path)

        default: dict[str, object] = {"top": {"nested1": 1, "nested2": 2}, "other": 10}
        user: dict[str, object] = {"top": {"nested2": 20, "nested3": 3}}

        merged = config.merge_configs(default, user)

        merged_top = cast(dict[str, object], merged["top"])
        assert merged_top["nested1"] == 1  # Preserved
        assert merged_top["nested2"] == 20  # Override
        assert merged_top["nested3"] == 3  # Added
        assert merged["other"] == 10  # Preserved

    def test_merge_with_type_mismatch(self, tmp_path: Path) -> None:
        """Test merging handles type mismatches correctly."""
        config = ValidationConfig(project_root=tmp_path)

        default: dict[str, object] = {"value": {"nested": 1}}
        user: dict[str, object] = {"value": 42}  # Type mismatch: dict vs int

        merged = config.merge_configs(default, user)

        # User value should completely replace default
        assert merged["value"] == 42


class TestGetConfigValue:
    """Tests for get method with dot notation."""

    def test_get_top_level_value(self, tmp_path: Path) -> None:
        """Test getting top-level config value."""
        config = ValidationConfig(project_root=tmp_path)

        assert config.get("enabled") == DEFAULT_CONFIG["enabled"]

    def test_get_nested_value(self, tmp_path: Path) -> None:
        """Test getting nested config value with dot notation."""
        config = ValidationConfig(project_root=tmp_path)

        value = config.get("token_budget.max_total_tokens")
        token_budget = cast(dict[str, object], DEFAULT_CONFIG["token_budget"])
        assert value == token_budget["max_total_tokens"]

    def test_get_deeply_nested_value(self, tmp_path: Path) -> None:
        """Test getting deeply nested config value."""
        config = ValidationConfig(project_root=tmp_path)

        value = config.get("quality.weights.completeness")
        quality = cast(dict[str, object], DEFAULT_CONFIG["quality"])
        weights = cast(dict[str, object], quality["weights"])
        assert value == weights["completeness"]

    def test_get_nonexistent_key_returns_default(self, tmp_path: Path) -> None:
        """Test getting nonexistent key returns default value."""
        config = ValidationConfig(project_root=tmp_path)

        value = config.get("nonexistent", "default_value")
        assert value == "default_value"

    def test_get_nonexistent_nested_key_returns_default(self, tmp_path: Path) -> None:
        """Test getting nonexistent nested key returns default."""
        config = ValidationConfig(project_root=tmp_path)

        value = config.get("token_budget.nonexistent", 999)
        assert value == 999


class TestSetConfigValue:
    """Tests for set method with dot notation."""

    def test_set_top_level_value(self, tmp_path: Path) -> None:
        """Test setting top-level config value."""
        config = ValidationConfig(project_root=tmp_path)

        config.set("enabled", False)
        assert config.config["enabled"] is False

    def test_set_nested_value(self, tmp_path: Path) -> None:
        """Test setting nested config value with dot notation."""
        config = ValidationConfig(project_root=tmp_path)

        config.set("token_budget.max_total_tokens", 200000)
        token_budget = cast(dict[str, object], config.config["token_budget"])
        assert token_budget["max_total_tokens"] == 200000

    def test_set_deeply_nested_value(self, tmp_path: Path) -> None:
        """Test setting deeply nested config value."""
        config = ValidationConfig(project_root=tmp_path)

        config.set("quality.weights.completeness", 0.5)
        quality = cast(dict[str, object], config.config["quality"])
        weights = cast(dict[str, object], quality["weights"])
        assert weights["completeness"] == 0.5

    def test_set_creates_intermediate_dicts(self, tmp_path: Path) -> None:
        """Test set creates intermediate dictionaries if needed."""
        config = ValidationConfig(project_root=tmp_path)

        config.set("new.nested.value", 42)
        new_dict = cast(dict[str, object], config.config["new"])
        nested = cast(dict[str, object], new_dict["nested"])
        assert nested["value"] == 42


class TestSaveConfig:
    """Tests for save method."""

    @pytest.mark.asyncio
    async def test_save_creates_config_file(self, tmp_path: Path) -> None:
        """Test save creates configuration file."""
        # Create .cortex directory
        (tmp_path / ".cortex").mkdir(parents=True, exist_ok=True)
        config = ValidationConfig(project_root=tmp_path)
        config.set("enabled", False)

        await config.save()

        assert config.config_path.exists()

    @pytest.mark.asyncio
    async def test_save_persists_changes(self, tmp_path: Path) -> None:
        """Test save persists configuration changes."""
        # Create .cortex directory
        (tmp_path / ".cortex").mkdir(parents=True, exist_ok=True)
        config = ValidationConfig(project_root=tmp_path)
        config.set("enabled", False)
        config.set("strict_mode", True)

        await config.save()

        # Load saved config
        with open(config.config_path) as f:
            saved_config = json.load(f)

        assert saved_config["enabled"] is False
        assert saved_config["strict_mode"] is True

    @pytest.mark.asyncio
    async def test_save_can_be_reloaded(self, tmp_path: Path) -> None:
        """Test saved config can be reloaded correctly."""
        # Create .cortex directory
        (tmp_path / ".cortex").mkdir(parents=True, exist_ok=True)
        # Save config
        config1 = ValidationConfig(project_root=tmp_path)
        config1.set("enabled", False)
        config1.set("token_budget.max_total_tokens", 200000)
        await config1.save()

        # Reload config in new instance
        config2 = ValidationConfig(project_root=tmp_path)

        assert config2.get("enabled") is False
        assert config2.get("token_budget.max_total_tokens") == 200000


class TestResetToDefaults:
    """Tests for reset_to_defaults method."""

    def test_reset_clears_custom_values(self, tmp_path: Path) -> None:
        """Test reset clears custom values and restores defaults."""
        config = ValidationConfig(project_root=tmp_path)

        # Modify config
        config.set("enabled", False)
        config.set("strict_mode", True)
        config.set("token_budget.max_total_tokens", 200000)

        # Reset
        config.reset_to_defaults()

        # Values should match defaults
        assert config.config == DEFAULT_CONFIG


class TestValidateConfig:
    """Tests for validate_config method."""

    def test_validate_valid_config_returns_no_errors(self, tmp_path: Path) -> None:
        """Test validate returns no errors for valid config."""
        config = ValidationConfig(project_root=tmp_path)

        errors = config.validate_config()
        assert len(errors) == 0

    def test_validate_invalid_enabled_type(self, tmp_path: Path) -> None:
        """Test validate detects invalid enabled type."""
        config = ValidationConfig(project_root=tmp_path)
        config.config["enabled"] = "not a boolean"

        errors = config.validate_config()
        assert len(errors) > 0
        assert any(
            "Invalid 'enabled' value" in err or "'enabled' must be" in err
            for err in errors
        )

    def test_validate_invalid_max_tokens(self, tmp_path: Path) -> None:
        """Test validate detects invalid max_total_tokens."""
        config = ValidationConfig(project_root=tmp_path)
        token_budget = cast(dict[str, object], config.config["token_budget"])
        token_budget["max_total_tokens"] = -1000

        errors = config.validate_config()
        assert len(errors) > 0
        assert any("positive integer" in err for err in errors)

    def test_validate_invalid_warn_percentage(self, tmp_path: Path) -> None:
        """Test validate detects invalid warn_at_percentage."""
        config = ValidationConfig(project_root=tmp_path)
        token_budget = cast(dict[str, object], config.config["token_budget"])
        token_budget["warn_at_percentage"] = 150

        errors = config.validate_config()
        assert len(errors) > 0
        assert any("between 0 and 100" in err for err in errors)

    def test_validate_invalid_duplication_threshold(self, tmp_path: Path) -> None:
        """Test validate detects invalid duplication threshold."""
        config = ValidationConfig(project_root=tmp_path)
        duplication = cast(dict[str, object], config.config["duplication"])
        duplication["threshold"] = 1.5

        errors = config.validate_config()
        assert len(errors) > 0
        assert any("between 0.0 and 1.0" in err for err in errors)

    def test_validate_invalid_quality_weights_sum(self, tmp_path: Path) -> None:
        """Test validate detects quality weights not summing to 1.0."""
        config = ValidationConfig(project_root=tmp_path)
        quality = cast(dict[str, object], config.config["quality"])
        quality["weights"] = {
            "completeness": 0.5,
            "consistency": 0.5,
            "freshness": 0.5,  # Sum > 1.0
        }

        errors = config.validate_config()
        assert len(errors) > 0
        assert any("sum to 1.0" in err or "Must sum to 1.0" in err for err in errors)

    def test_validate_multiple_errors(self, tmp_path: Path) -> None:
        """Test validate collects multiple errors."""
        config = ValidationConfig(project_root=tmp_path)
        config.config["enabled"] = "invalid"
        token_budget = cast(dict[str, object], config.config["token_budget"])
        token_budget["max_total_tokens"] = -1
        duplication = cast(dict[str, object], config.config["duplication"])
        duplication["threshold"] = 2.0

        errors = config.validate_config()
        assert len(errors) >= 3


class TestHelperMethods:
    """Tests for convenience helper methods."""

    def test_is_validation_enabled(self, tmp_path: Path) -> None:
        """Test is_validation_enabled returns correct value."""
        config = ValidationConfig(project_root=tmp_path)

        assert config.is_validation_enabled() == DEFAULT_CONFIG["enabled"]

        config.set("enabled", False)
        assert config.is_validation_enabled() is False

    def test_is_auto_validate_enabled(self, tmp_path: Path) -> None:
        """Test is_auto_validate_enabled returns correct value."""
        config = ValidationConfig(project_root=tmp_path)

        assert (
            config.is_auto_validate_enabled()
            == DEFAULT_CONFIG["auto_validate_on_write"]
        )

        config.set("auto_validate_on_write", False)
        assert config.is_auto_validate_enabled() is False

    def test_is_strict_mode(self, tmp_path: Path) -> None:
        """Test is_strict_mode returns correct value."""
        config = ValidationConfig(project_root=tmp_path)

        assert config.is_strict_mode() == DEFAULT_CONFIG["strict_mode"]

        config.set("strict_mode", True)
        assert config.is_strict_mode() is True

    def test_get_token_budget_max(self, tmp_path: Path) -> None:
        """Test get_token_budget_max returns correct value."""
        config = ValidationConfig(project_root=tmp_path)

        token_budget = cast(dict[str, object], DEFAULT_CONFIG["token_budget"])
        expected = token_budget["max_total_tokens"]
        assert config.get_token_budget_max() == expected

        config.set("token_budget.max_total_tokens", 200000)
        assert config.get_token_budget_max() == 200000

    def test_get_token_budget_warn_threshold(self, tmp_path: Path) -> None:
        """Test get_token_budget_warn_threshold returns correct value."""
        config = ValidationConfig(project_root=tmp_path)

        token_budget = cast(dict[str, object], DEFAULT_CONFIG["token_budget"])
        expected = token_budget["warn_at_percentage"]
        assert config.get_token_budget_warn_threshold() == expected

        config.set("token_budget.warn_at_percentage", 90)
        assert config.get_token_budget_warn_threshold() == 90

    def test_get_duplication_threshold(self, tmp_path: Path) -> None:
        """Test get_duplication_threshold returns correct value."""
        config = ValidationConfig(project_root=tmp_path)

        duplication = cast(dict[str, object], DEFAULT_CONFIG["duplication"])
        expected = duplication["threshold"]
        assert config.get_duplication_threshold() == expected

        config.set("duplication.threshold", 0.9)
        assert config.get_duplication_threshold() == 0.9

    def test_get_quality_minimum_score(self, tmp_path: Path) -> None:
        """Test get_quality_minimum_score returns correct value."""
        config = ValidationConfig(project_root=tmp_path)

        quality_config = cast(dict[str, object], DEFAULT_CONFIG["quality"])
        expected = cast(int, quality_config["minimum_score"])
        assert config.get_quality_minimum_score() == expected

        config.set("quality.minimum_score", 80)
        assert config.get_quality_minimum_score() == 80


class TestToDict:
    """Tests for to_dict method."""

    def test_to_dict_returns_copy(self, tmp_path: Path) -> None:
        """Test to_dict returns a copy of config."""
        config = ValidationConfig(project_root=tmp_path)

        config_dict = config.to_dict()

        # Modifying returned dict should not affect original
        config_dict["enabled"] = False
        assert config.config["enabled"]

    def test_to_dict_contains_all_keys(self, tmp_path: Path) -> None:
        """Test to_dict returns complete configuration."""
        config = ValidationConfig(project_root=tmp_path)

        config_dict = config.to_dict()

        assert "enabled" in config_dict
        assert "token_budget" in config_dict
        assert "duplication" in config_dict
        assert "quality" in config_dict
        assert "schemas" in config_dict
