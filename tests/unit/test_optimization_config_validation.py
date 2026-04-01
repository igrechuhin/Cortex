"""Unit tests for OptimizationConfig validation, edge cases, and utility methods.

Split from test_optimization_config.py to stay under 400 lines per file.
"""

from pathlib import Path

import pytest

from cortex.optimization.config import OptimizationConfig


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_validate_returns_true_for_valid_config(
        self, temp_project_root: Path
    ) -> None:
        """Test validate returns True for valid configuration."""
        config = OptimizationConfig(temp_project_root)
        is_valid, error = config.validate()
        assert is_valid is True
        assert error is None

    def test_validate_rejects_negative_default_budget(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects negative default budget."""
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.default_budget", -1000)
        is_valid, error = config.validate()
        assert is_valid is False
        assert error is not None and "positive integer" in error

    def test_validate_rejects_non_integer_budget(self, temp_project_root: Path) -> None:
        """Test validate rejects non-integer budget."""
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.default_budget", "invalid")
        is_valid, error = config.validate()
        assert is_valid is False
        assert error is not None and "positive integer" in error

    def test_validate_rejects_default_exceeding_max(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects default budget exceeding max."""
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.default_budget", 150000)
        _ = config.set("token_budget.max_budget", 100000)
        is_valid, error = config.validate()
        assert is_valid is False
        assert error is not None and "cannot exceed max_budget" in error

    def test_validate_rejects_invalid_loading_strategy(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects invalid loading strategy."""
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.default_budget", 80000)
        _ = config.set("token_budget.max_budget", 100000)
        _ = config.set("loading_strategy.default", "invalid_strategy")
        is_valid, error = config.validate()
        assert is_valid is False
        assert error is not None and "must be one of" in error

    def test_validate_rejects_invalid_target_reduction(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects invalid target reduction."""
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.default_budget", 80000)
        _ = config.set("token_budget.max_budget", 100000)
        _ = config.set("loading_strategy.default", "dependency_aware")
        _ = config.set("summarization.target_reduction", 1.5)
        is_valid, error = config.validate()
        assert is_valid is False
        assert error is not None and "between 0 and 1" in error

    def test_validate_rejects_unbalanced_relevance_weights(
        self, temp_project_root: Path
    ) -> None:
        """Test validate rejects relevance weights not summing to 1.0."""
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.default_budget", 80000)
        _ = config.set("token_budget.max_budget", 100000)
        _ = config.set("loading_strategy.default", "dependency_aware")
        _ = config.set("summarization.target_reduction", 0.5)
        _ = config.set("relevance.keyword_weight", 0.8)
        _ = config.set("relevance.dependency_weight", 0.8)
        is_valid, error = config.validate()
        assert is_valid is False
        assert error is not None and "must sum to ~1.0" in error


class TestConfigUtilityMethods:
    """Tests for utility methods."""

    def test_to_dict_returns_copy_of_config(self, temp_project_root: Path) -> None:
        """Test to_dict returns dictionary copy."""
        config = OptimizationConfig(temp_project_root)
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict == config.config
        config_dict["modified"] = True
        assert "modified" not in config.config

    def test_repr_returns_string_representation(self, temp_project_root: Path) -> None:
        """Test __repr__ returns string representation."""
        config = OptimizationConfig(temp_project_root)
        repr_str = repr(config)
        assert isinstance(repr_str, str)
        assert "OptimizationConfig" in repr_str
        assert str(temp_project_root) in repr_str


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_handles_deeply_nested_config_paths(self, temp_project_root: Path) -> None:
        """Test handles deeply nested configuration paths."""
        config = OptimizationConfig(temp_project_root)
        _ = config.set("a.b.c.d.e.f", "deep_value")
        value = config.get("a.b.c.d.e.f")
        assert value == "deep_value"

    def test_handles_special_characters_in_values(
        self, temp_project_root: Path
    ) -> None:
        """Test handles special characters in configuration values."""
        config = OptimizationConfig(temp_project_root)
        special_value = "test@#$%^&*()[]{}|\\:;\"'<>,.?/~`"
        _ = config.set("test.key", special_value)
        assert config.get("test.key") == special_value

    @pytest.mark.asyncio
    async def test_preserves_config_types_through_save_load(
        self, temp_project_root: Path
    ) -> None:
        """Test configuration types preserved through save/load cycle."""
        config = OptimizationConfig(temp_project_root)
        _ = config.set("test.int", 42)
        _ = config.set("test.float", 3.14)
        _ = config.set("test.bool", True)
        _ = config.set("test.list", [1, 2, 3])
        _ = config.set("test.dict", {"nested": "value"})
        _ = await config.save_config()
        new_config = OptimizationConfig(temp_project_root)
        assert isinstance(new_config.get("test.int"), int)
        assert isinstance(new_config.get("test.float"), float)
        assert isinstance(new_config.get("test.bool"), bool)
        assert isinstance(new_config.get("test.list"), list)
        assert isinstance(new_config.get("test.dict"), dict)
