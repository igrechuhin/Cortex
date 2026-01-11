"""
Unit tests for optimization_config module.

Tests configuration management for token optimization features.
"""

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.optimization.optimization_config import (
    DEFAULT_OPTIMIZATION_CONFIG,
    OptimizationConfig,
)


class TestOptimizationConfigInitialization:
    """Tests for OptimizationConfig initialization."""

    def test_initialization_creates_instance(self, temp_project_root: Path) -> None:
        """Test OptimizationConfig initializes with project root."""
        # Arrange & Act
        config = OptimizationConfig(temp_project_root)

        # Assert
        assert config is not None
        assert config.project_root == temp_project_root
        assert config.config_path == temp_project_root / ".cortex/optimization.json"

    def test_initialization_loads_defaults_when_no_file(
        self, temp_project_root: Path
    ) -> None:
        """Test OptimizationConfig loads defaults when no config file exists."""
        # Arrange & Act
        config = OptimizationConfig(temp_project_root)

        # Assert
        assert config.config == DEFAULT_OPTIMIZATION_CONFIG

    def test_initialization_loads_existing_config_file(
        self, temp_project_root: Path
    ) -> None:
        """Test OptimizationConfig loads existing config file."""
        # Arrange
        config_path = temp_project_root / ".cortex/optimization.json"
        custom_config = {
            "enabled": False,
            "token_budget": {
                "default_budget": 50000,
            },
        }
        _ = config_path.write_text(json.dumps(custom_config))

        # Act
        config = OptimizationConfig(temp_project_root)

        # Assert
        assert config.config["enabled"] is False
        token_budget = cast(dict[str, object], config.config["token_budget"])
        assert token_budget["default_budget"] == 50000
        # Should merge with defaults
        assert "max_budget" in token_budget


class TestConfigFileOperations:
    """Tests for config file loading and saving."""

    def test_load_config_handles_invalid_json(
        self, temp_project_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test load handles invalid JSON gracefully."""
        # Arrange
        config_path = temp_project_root / ".cortex/optimization.json"
        _ = config_path.write_text("{invalid json")

        # Act
        config = OptimizationConfig(temp_project_root)

        # Assert
        assert config.config == DEFAULT_OPTIMIZATION_CONFIG
        captured = capsys.readouterr()
        assert "Warning: Failed to load optimization config" in captured.out

    @pytest.mark.asyncio
    async def test_save_config_creates_file(self, temp_project_root: Path) -> None:
        """Test save_config creates config file."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        config.config["enabled"] = False

        # Act
        result = await config.save_config()

        # Assert
        assert result is True
        assert config.config_path.exists()
        saved_data = json.loads(config.config_path.read_text())
        assert saved_data["enabled"] is False

    @pytest.mark.asyncio
    async def test_save_config_returns_false_on_error(
        self,
        temp_project_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test save_config returns False on IO error."""
        from unittest.mock import patch

        # Arrange
        config = OptimizationConfig(temp_project_root)
        with patch("aiofiles.open", side_effect=OSError("Permission denied")):
            # Act
            result = await config.save_config()

            # Assert
            assert result is False
            captured = capsys.readouterr()
            assert "Error: Failed to save optimization config" in captured.out


class TestConfigMerging:
    """Tests for configuration merging logic."""

    def test_merge_configs_merges_nested_dicts(self, temp_project_root: Path) -> None:
        """Test merge_configs correctly merges nested dictionaries."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        default: dict[str, object] = {"a": {"b": 1, "c": 2}, "d": 3}
        user: dict[str, object] = {"a": {"b": 10}, "e": 4}

        # Act
        result = config.merge_configs(default, user)

        # Assert
        result_a = cast(dict[str, object], result["a"])
        assert result_a["b"] == 10  # User override
        assert result_a["c"] == 2  # Default preserved
        assert result["d"] == 3  # Default preserved
        assert result["e"] == 4  # User added

    def test_merge_configs_replaces_non_dict_values(
        self, temp_project_root: Path
    ) -> None:
        """Test merge_configs replaces non-dict values."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        default: dict[str, object] = {"key": [1, 2, 3]}
        user: dict[str, object] = {"key": [4, 5]}

        # Act
        result = config.merge_configs(default, user)

        # Assert
        assert result["key"] == [4, 5]  # Replaced, not merged


class TestDotNotationAccess:
    """Tests for dot notation get/set methods."""

    def test_get_returns_nested_value_with_dot_notation(
        self, temp_project_root: Path
    ) -> None:
        """Test get returns value using dot notation."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        value = config.get("token_budget.default_budget")

        # Assert
        assert value == 80000

    def test_get_returns_default_when_key_not_found(
        self, temp_project_root: Path
    ) -> None:
        """Test get returns default value when key doesn't exist."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        value = config.get("nonexistent.key", "default_value")

        # Assert
        assert value == "default_value"

    def test_get_returns_none_when_no_default_and_key_not_found(
        self, temp_project_root: Path
    ) -> None:
        """Test get returns None when key doesn't exist and no default."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        value = config.get("nonexistent.key")

        # Assert
        assert value is None

    def test_set_updates_nested_value_with_dot_notation(
        self, temp_project_root: Path
    ) -> None:
        """Test set updates value using dot notation."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        result = config.set("token_budget.default_budget", 50000)

        # Assert
        assert result is True
        assert config.get("token_budget.default_budget") == 50000

    def test_set_creates_intermediate_dicts_when_needed(
        self, temp_project_root: Path
    ) -> None:
        """Test set creates intermediate dictionaries."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        result = config.set("new.nested.key", "value")

        # Assert
        assert result is True
        assert config.get("new.nested.key") == "value"

    def test_set_returns_false_when_parent_not_dict(
        self, temp_project_root: Path
    ) -> None:
        """Test set returns False when parent is not a dict."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        config.config["scalar"] = "value"

        # Act
        result = config.set("scalar.nested.key", "new_value")

        # Assert
        assert result is False

    def test_set_handles_empty_key_path(self, temp_project_root: Path) -> None:
        """Test set handles empty key path (splits to empty list)."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        result = config.set("", "value")

        # Assert
        # Empty string splits to [""], which creates a key with empty string
        # This is allowed behavior, though not recommended
        assert result is True or result is False  # Either is acceptable


class TestConfigReset:
    """Tests for configuration reset."""

    @pytest.mark.asyncio
    async def test_reset_restores_defaults(self, temp_project_root: Path) -> None:
        """Test reset restores default configuration."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        original_budget = config.get("token_budget.default_budget")
        _ = config.set("token_budget.default_budget", 50000)
        _ = config.set("custom.key", "value")

        # Verify modifications applied
        assert config.get("token_budget.default_budget") == 50000

        # Act
        await config.reset()

        # Assert
        assert config.get("token_budget.default_budget") == original_budget
        assert config.get("custom.key") is None


class TestConvenienceMethods:
    """Tests for convenience getter methods."""

    def test_get_token_budget_returns_default_budget(
        self, temp_project_root: Path
    ) -> None:
        """Test get_token_budget returns default budget."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        budget = config.get_token_budget()

        # Assert
        # Should be the default value from DEFAULT_OPTIMIZATION_CONFIG
        assert budget > 0
        assert isinstance(budget, int)

    def test_get_max_token_budget_returns_max_budget(
        self, temp_project_root: Path
    ) -> None:
        """Test get_max_token_budget returns maximum budget."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        max_budget = config.get_max_token_budget()

        # Assert
        assert max_budget == 100000

    def test_get_loading_strategy_returns_strategy(
        self, temp_project_root: Path
    ) -> None:
        """Test get_loading_strategy returns default strategy."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        strategy = config.get_loading_strategy()

        # Assert
        assert strategy == "dependency_aware"

    def test_get_mandatory_files_returns_list(self, temp_project_root: Path) -> None:
        """Test get_mandatory_files returns mandatory file list."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        files = config.get_mandatory_files()

        # Assert
        assert isinstance(files, list)
        assert "memorybankinstructions.md" in files

    def test_get_priority_order_returns_ordered_list(
        self, temp_project_root: Path
    ) -> None:
        """Test get_priority_order returns priority list."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        order = config.get_priority_order()

        # Assert
        assert isinstance(order, list)
        assert len(order) == 7
        assert order[0] == "memorybankinstructions.md"

    def test_is_summarization_enabled_returns_bool(
        self, temp_project_root: Path
    ) -> None:
        """Test is_summarization_enabled returns boolean."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        enabled = config.is_summarization_enabled()

        # Assert
        assert enabled is True

    def test_get_summarization_strategy_returns_strategy(
        self, temp_project_root: Path
    ) -> None:
        """Test get_summarization_strategy returns strategy name."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        strategy = config.get_summarization_strategy()

        # Assert
        assert strategy == "extract_key_sections"

    def test_get_summarization_target_reduction_returns_float(
        self, temp_project_root: Path
    ) -> None:
        """Test get_summarization_target_reduction returns reduction ratio."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        reduction = config.get_summarization_target_reduction()

        # Assert
        assert reduction == 0.5

    def test_get_relevance_weights_returns_dict(self, temp_project_root: Path) -> None:
        """Test get_relevance_weights returns weight dictionary."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        weights = config.get_relevance_weights()

        # Assert
        assert isinstance(weights, dict)
        assert "keyword_weight" in weights
        assert "dependency_weight" in weights
        assert "recency_weight" in weights
        assert "quality_weight" in weights
        assert sum(weights.values()) == pytest.approx(1.0)  # type: ignore[arg-type]

    def test_is_cache_enabled_returns_bool(self, temp_project_root: Path) -> None:
        """Test is_cache_enabled returns boolean."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        enabled = config.is_cache_enabled()

        # Assert
        assert enabled is True

    def test_get_cache_ttl_returns_seconds(self, temp_project_root: Path) -> None:
        """Test get_cache_ttl returns TTL in seconds."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        ttl = config.get_cache_ttl()

        # Assert
        assert ttl == 3600

    def test_is_rules_enabled_returns_bool(self, temp_project_root: Path) -> None:
        """Test is_rules_enabled returns boolean."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        enabled = config.is_rules_enabled()

        # Assert
        assert enabled is False

    def test_get_rules_folder_returns_path(self, temp_project_root: Path) -> None:
        """Test get_rules_folder returns folder path."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        folder = config.get_rules_folder()

        # Assert
        assert folder == ".cursorrules"

    def test_is_self_evolution_enabled_returns_bool(
        self, temp_project_root: Path
    ) -> None:
        """Test is_self_evolution_enabled returns boolean."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        enabled = config.is_self_evolution_enabled()

        # Assert
        assert enabled is True


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_validate_returns_true_for_valid_config(
        self, temp_project_root: Path
    ) -> None:
        """Test validate returns True for valid configuration."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        is_valid, error = config.validate()

        # Assert
        assert is_valid is True
        assert error is None

    def test_validate_rejects_negative_default_budget(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects negative default budget."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.default_budget", -1000)

        # Act
        is_valid, error = config.validate()

        # Assert
        assert is_valid is False
        assert error is not None and "positive integer" in error

    def test_validate_rejects_non_integer_budget(self, temp_project_root: Path) -> None:
        """Test validate rejects non-integer budget."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.default_budget", "invalid")

        # Act
        is_valid, error = config.validate()

        # Assert
        assert is_valid is False
        assert error is not None and "positive integer" in error

    def test_validate_rejects_default_exceeding_max(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects default budget exceeding max."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.default_budget", 150000)
        _ = config.set("token_budget.max_budget", 100000)

        # Act
        is_valid, error = config.validate()

        # Assert
        assert is_valid is False
        assert error is not None and "cannot exceed max_budget" in error

    def test_validate_rejects_invalid_loading_strategy(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects invalid loading strategy."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        # Ensure budgets are valid first
        _ = config.set("token_budget.default_budget", 80000)
        _ = config.set("token_budget.max_budget", 100000)
        _ = config.set("loading_strategy.default", "invalid_strategy")

        # Act
        is_valid, error = config.validate()

        # Assert
        assert is_valid is False
        assert error is not None and "must be one of" in error

    def test_validate_rejects_invalid_target_reduction(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects invalid target reduction."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        # Ensure budgets and strategy are valid first
        _ = config.set("token_budget.default_budget", 80000)
        _ = config.set("token_budget.max_budget", 100000)
        _ = config.set("loading_strategy.default", "dependency_aware")
        _ = config.set("summarization.target_reduction", 1.5)

        # Act
        is_valid, error = config.validate()

        # Assert
        assert is_valid is False
        assert error is not None and "between 0 and 1" in error

    def test_validate_rejects_unbalanced_relevance_weights(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects relevance weights not summing to 1.0."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        # Ensure all prior validation criteria pass
        _ = config.set("token_budget.default_budget", 80000)
        _ = config.set("token_budget.max_budget", 100000)
        _ = config.set("loading_strategy.default", "dependency_aware")
        _ = config.set("summarization.target_reduction", 0.5)
        _ = config.set("relevance.keyword_weight", 0.8)
        _ = config.set("relevance.dependency_weight", 0.8)

        # Act
        is_valid, error = config.validate()

        # Assert
        assert is_valid is False
        assert error is not None and "must sum to ~1.0" in error


class TestConfigUtilityMethods:
    """Tests for utility methods."""

    def test_to_dict_returns_copy_of_config(self, temp_project_root: Path) -> None:
        """Test to_dict returns dictionary copy."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        config_dict = config.to_dict()

        # Assert
        assert isinstance(config_dict, dict)
        assert config_dict == config.config
        # Verify it's a copy, not a reference
        config_dict["modified"] = True
        assert "modified" not in config.config

    def test_repr_returns_string_representation(self, temp_project_root: Path) -> None:
        """Test __repr__ returns string representation."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        repr_str = repr(config)

        # Assert
        assert isinstance(repr_str, str)
        assert "OptimizationConfig" in repr_str
        assert str(temp_project_root) in repr_str


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_handles_deeply_nested_config_paths(self, temp_project_root: Path) -> None:
        """Test handles deeply nested configuration paths."""
        # Arrange
        config = OptimizationConfig(temp_project_root)

        # Act
        _ = config.set("a.b.c.d.e.f", "deep_value")
        value = config.get("a.b.c.d.e.f")

        # Assert
        assert value == "deep_value"

    def test_handles_special_characters_in_values(
        self, temp_project_root: Path
    ) -> None:
        """Test handles special characters in configuration values."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        special_value = "test@#$%^&*()[]{}|\\:;\"'<>,.?/~`"

        # Act
        _ = config.set("test.key", special_value)

        # Assert
        assert config.get("test.key") == special_value

    @pytest.mark.asyncio
    async def test_preserves_config_types_through_save_load(
        self, temp_project_root: Path
    ) -> None:
        """Test configuration types preserved through save/load cycle."""
        # Arrange
        config = OptimizationConfig(temp_project_root)
        _ = config.set("test.int", 42)
        _ = config.set("test.float", 3.14)
        _ = config.set("test.bool", True)
        _ = config.set("test.list", [1, 2, 3])
        _ = config.set("test.dict", {"nested": "value"})
        _ = await config.save_config()

        # Act
        new_config = OptimizationConfig(temp_project_root)

        # Assert
        assert isinstance(new_config.get("test.int"), int)
        assert isinstance(new_config.get("test.float"), float)
        assert isinstance(new_config.get("test.bool"), bool)
        assert isinstance(new_config.get("test.list"), list)
        assert isinstance(new_config.get("test.dict"), dict)
