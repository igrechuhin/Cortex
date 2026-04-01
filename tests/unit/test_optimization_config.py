"""Unit tests for optimization_config module -- core operations.

Tests configuration management for token optimization features.
Getter tests live in test_optimization_config_getters.py;
validation/edge-case tests live in test_optimization_config_validation.py.
"""

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.optimization.config import (
    DEFAULT_OPTIMIZATION_CONFIG,
    OptimizationConfig,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockAsyncContextManager:
    """Mock async context manager that raises OSError."""

    async def __aenter__(self) -> object:
        raise OSError("Permission denied")

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_open_async_text_file(*args: object, **kwargs: object) -> object:
    """Mock that returns async context manager raising OSError."""
    return _MockAsyncContextManager()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestOptimizationConfigInitialization:
    """Tests for OptimizationConfig initialization."""

    def test_initialization_creates_instance(self, temp_project_root: Path) -> None:
        """Test OptimizationConfig initializes with project root."""
        config = OptimizationConfig(temp_project_root)
        assert config is not None
        assert config.project_root == temp_project_root
        expected_config_path = (
            get_cortex_path(temp_project_root, CortexResourceType.CONFIG)
            / "optimization.json"
        )
        assert config.config_path == expected_config_path

    def test_loads_defaults_when_no_file(self, temp_project_root: Path) -> None:
        """Test OptimizationConfig loads defaults when no config file."""
        config = OptimizationConfig(temp_project_root)
        for key in DEFAULT_OPTIMIZATION_CONFIG:
            assert key in config.config, f"Missing key {key}"
        tool_search = config.config.get("tool_search")
        assert isinstance(tool_search, dict)
        assert "enabled" in tool_search
        assert "always_loaded" in tool_search
        assert "deferred_medium" in tool_search
        assert "deferred_low" in tool_search

    def test_loads_existing_config_file(self, temp_project_root: Path) -> None:
        """Test OptimizationConfig loads existing config file."""
        config_path = (
            get_cortex_path(temp_project_root, CortexResourceType.CONFIG)
            / "optimization.json"
        )
        config_path.parent.mkdir(parents=True, exist_ok=True)
        custom_config = {
            "enabled": False,
            "token_budget": {"default_budget": 50000},
        }
        _ = config_path.write_text(json.dumps(custom_config))
        config = OptimizationConfig(temp_project_root)
        assert config.config["enabled"] is False
        token_budget = cast(dict[str, object], config.config["token_budget"])
        assert token_budget["default_budget"] == 50000
        assert "max_budget" in token_budget


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


class TestConfigFileOperations:
    """Tests for config file loading and saving."""

    def test_load_handles_invalid_json(
        self, temp_project_root: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test load handles invalid JSON gracefully."""
        import logging

        config_path = (
            get_cortex_path(temp_project_root, CortexResourceType.CONFIG)
            / "optimization.json"
        )
        config_path.parent.mkdir(parents=True, exist_ok=True)
        _ = config_path.write_text("{invalid json")
        with caplog.at_level(logging.WARNING):
            config = OptimizationConfig(temp_project_root)
        for key in DEFAULT_OPTIMIZATION_CONFIG:
            assert key in config.config, f"Missing key {key}"
        assert isinstance(config.config.get("tool_search"), dict)
        if caplog.records:
            msgs = [r.message for r in caplog.records]
            assert any("optimization config" in m.lower() for m in msgs)

    @pytest.mark.asyncio
    async def test_save_config_creates_file(self, temp_project_root: Path) -> None:
        """Test save_config creates config file."""
        config = OptimizationConfig(temp_project_root)
        config.config["enabled"] = False
        result = await config.save_config()
        assert result is True
        assert config.config_path.exists()
        saved = json.loads(config.config_path.read_text())
        assert saved["enabled"] is False

    @pytest.mark.asyncio
    async def test_save_config_returns_false_on_error(
        self,
        temp_project_root: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test save_config returns False on IO error."""
        import logging
        from unittest.mock import patch

        config = OptimizationConfig(temp_project_root)
        with (
            patch(
                "cortex.optimization.config_loading.open_async_text_file",
                side_effect=_mock_open_async_text_file,
            ),
            caplog.at_level(logging.ERROR),
        ):
            result = await config.save_config()
            assert result is False
            if caplog.records:
                msgs = [r.message for r in caplog.records]
                assert any("optimization config" in m.lower() for m in msgs)


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------


class TestConfigMerging:
    """Tests for configuration merging logic."""

    def test_merges_nested_dicts(self, temp_project_root: Path) -> None:
        """Test merge_configs correctly merges nested dictionaries."""
        config = OptimizationConfig(temp_project_root)
        default = cast(ModelDict, {"a": {"b": 1, "c": 2}, "d": 3})
        user = cast(ModelDict, {"a": {"b": 10}, "e": 4})
        result = config.merge_configs(default, user)
        result_a = cast(dict[str, object], result["a"])
        assert result_a["b"] == 10
        assert result_a["c"] == 2
        assert result["d"] == 3
        assert result["e"] == 4

    def test_replaces_non_dict_values(self, temp_project_root: Path) -> None:
        """Test merge_configs replaces non-dict values."""
        config = OptimizationConfig(temp_project_root)
        default = cast(ModelDict, {"key": [1, 2, 3]})
        user = cast(ModelDict, {"key": [4, 5]})
        result = config.merge_configs(default, user)
        assert result["key"] == [4, 5]


# ---------------------------------------------------------------------------
# Dot-notation access
# ---------------------------------------------------------------------------


class TestDotNotationAccess:
    """Tests for dot notation get/set methods."""

    def test_get_returns_nested_value(self, temp_project_root: Path) -> None:
        """Test get returns value using dot notation."""
        config = OptimizationConfig(temp_project_root)
        value = config.get("token_budget.default_budget")
        assert value == 80000

    def test_get_returns_default_when_key_not_found(
        self, temp_project_root: Path
    ) -> None:
        """Test get returns default value when key missing."""
        config = OptimizationConfig(temp_project_root)
        value = config.get("nonexistent.key", "default_value")
        assert value == "default_value"

    def test_get_returns_none_when_no_default(self, temp_project_root: Path) -> None:
        """Test get returns None when key missing and no default."""
        config = OptimizationConfig(temp_project_root)
        value = config.get("nonexistent.key")
        assert value is None

    def test_set_updates_nested_value(self, temp_project_root: Path) -> None:
        """Test set updates value using dot notation."""
        config = OptimizationConfig(temp_project_root)
        result = config.set("token_budget.default_budget", 50000)
        assert result is True
        assert config.get("token_budget.default_budget") == 50000

    def test_set_creates_intermediate_dicts(self, temp_project_root: Path) -> None:
        """Test set creates intermediate dictionaries."""
        config = OptimizationConfig(temp_project_root)
        result = config.set("new.nested.key", "value")
        assert result is True
        assert config.get("new.nested.key") == "value"

    def test_set_returns_false_when_parent_not_dict(
        self, temp_project_root: Path
    ) -> None:
        """Test set returns False when parent is not a dict."""
        config = OptimizationConfig(temp_project_root)
        config.config["scalar"] = "value"
        result = config.set("scalar.nested.key", "new_value")
        assert result is False

    def test_set_handles_empty_key_path(self, temp_project_root: Path) -> None:
        """Test set handles empty key path."""
        config = OptimizationConfig(temp_project_root)
        result = config.set("", "value")
        assert result is True


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestConfigReset:
    """Tests for configuration reset."""

    @pytest.mark.asyncio
    async def test_reset_restores_defaults(self, temp_project_root: Path) -> None:
        """Test reset restores default configuration."""
        config = OptimizationConfig(temp_project_root)
        original_budget = config.get("token_budget.default_budget")
        _ = config.set("token_budget.default_budget", 50000)
        _ = config.set("custom.key", "value")
        assert config.get("token_budget.default_budget") == 50000
        await config.reset()
        assert config.get("token_budget.default_budget") == original_budget
        assert config.get("custom.key") is None
