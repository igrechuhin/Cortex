"""Tests for configuration operations module."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import JsonValue, ModelDict
from cortex.tools.configuration_operations import (
    apply_config_updates,
    configure,
    configure_learning,
    configure_optimization,
    configure_validation,
    create_error_response,
    create_success_response,
    export_learned_patterns,
    get_learned_patterns,
    handle_learning_reset,
    handle_learning_update,
    handle_learning_view,
    handle_optimization_reset,
    handle_optimization_update,
    handle_validation_reset,
    handle_validation_update,
)
from tests.helpers.managers import make_test_managers


class TestConfigureMainHandler:
    """Test main configure handler."""

    @pytest.mark.asyncio
    async def test_configure_validation_view(self, tmp_path: Path) -> None:
        """Test viewing validation configuration."""
        # Arrange
        with patch(
            "cortex.tools.configuration_operations.get_managers"
        ) as mock_get_managers:
            mock_validation_config = MagicMock()
            mock_validation_config.config = MagicMock()
            mock_validation_config.config.model_dump.return_value = {
                "enabled": True,
                "strict_mode": False,
            }
            mock_get_managers.return_value = make_test_managers(
                validation_config=mock_validation_config
            )

            # Act
            result = await configure(
                component="validation",
                action="view",
                project_root=str(tmp_path),
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["component"] == "validation"
            assert "configuration" in result_data
            assert result_data["configuration"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_configure_optimization_view(self, tmp_path: Path) -> None:
        """Test viewing optimization configuration."""
        # Arrange
        with patch(
            "cortex.tools.configuration_operations.get_managers"
        ) as mock_get_managers:
            mock_optimization_config = MagicMock()
            mock_optimization_config.to_dict.return_value = {
                "enabled": True,
                "token_budget": {"default_budget": 100000},
            }
            mock_get_managers.return_value = make_test_managers(
                optimization_config=mock_optimization_config
            )

            # Act
            result = await configure(
                component="optimization",
                action="view",
                project_root=str(tmp_path),
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["component"] == "optimization"
            assert "configuration" in result_data

    @pytest.mark.asyncio
    async def test_configure_learning_view(self, tmp_path: Path) -> None:
        """Test viewing learning configuration."""
        # Arrange
        with patch(
            "cortex.tools.configuration_operations.get_managers"
        ) as mock_get_managers:
            mock_learning_engine = MagicMock()
            mock_learning_engine.data_manager.get_all_patterns.return_value = {}

            mock_optimization_config = MagicMock()
            mock_optimization_config.config = {"learning": {"enabled": True}}

            mock_get_managers.return_value = make_test_managers(
                learning_engine=mock_learning_engine,
                optimization_config=mock_optimization_config,
            )

            # Act
            result = await configure(
                component="learning",
                action="view",
                project_root=str(tmp_path),
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["component"] == "learning"
            assert "configuration" in result_data
            assert "learned_patterns" in result_data

    @pytest.mark.asyncio
    async def test_configure_unknown_component(self, tmp_path: Path) -> None:
        """Test configure with unknown component returns error."""
        # Arrange
        with patch(
            "cortex.tools.configuration_operations.get_managers"
        ) as mock_get_managers:
            mock_get_managers.return_value = {}

            # Act
            result = await configure(
                component="unknown",  # type: ignore[arg-type]
                action="view",
                project_root=str(tmp_path),
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Unknown component" in result_data["error"]
            assert "valid_components" in result_data

    @pytest.mark.asyncio
    async def test_configure_exception_handling(self, tmp_path: Path) -> None:
        """Test configure handles exceptions gracefully."""
        # Arrange
        with patch(
            "cortex.tools.configuration_operations.get_managers"
        ) as mock_get_managers:
            mock_get_managers.side_effect = RuntimeError("Test error")

            # Act
            result = await configure(
                component="validation",
                action="view",
                project_root=str(tmp_path),
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Test error" in result_data["error"]
            assert result_data["error_type"] == "RuntimeError"


class TestValidationConfiguration:
    """Test validation configuration helpers."""

    @pytest.mark.asyncio
    async def test_configure_validation_view(self) -> None:
        """Test validation view action."""
        # Arrange
        mock_validation_config = MagicMock()
        mock_validation_config.config = MagicMock()
        mock_validation_config.config.model_dump.return_value = {
            "enabled": True,
            "strict_mode": False,
        }
        mgrs = make_test_managers(validation_config=mock_validation_config)

        # Act
        result = await configure_validation(mgrs, "view", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["component"] == "validation"
        assert result_data["configuration"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_configure_validation_update_with_settings(self) -> None:
        """Test validation update with settings dict."""
        # Arrange
        mock_validation_config = MagicMock()
        mock_validation_config.config = MagicMock()
        mock_validation_config.config.model_dump.return_value = {
            "enabled": True,
            "strict_mode": True,
        }
        mock_validation_config.save = AsyncMock()
        mgrs = make_test_managers(validation_config=mock_validation_config)

        settings: dict[str, JsonValue] = {"strict_mode": True, "enabled": True}

        # Act
        result = await configure_validation(
            mgrs,
            "update",
            settings,
            None,
            None,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["message"] == "Configuration updated"
        mock_validation_config.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_validation_update_with_key_value(self) -> None:
        """Test validation update with key and value."""
        # Arrange
        mock_validation_config = MagicMock()
        mock_validation_config.config = MagicMock()
        mock_validation_config.config.model_dump.return_value = {
            "enabled": True,
            "strict_mode": True,
        }
        mock_validation_config.save = AsyncMock()
        mgrs = make_test_managers(validation_config=mock_validation_config)

        # Act
        result = await configure_validation(mgrs, "update", None, "strict_mode", True)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["message"] == "Configuration updated"
        mock_validation_config.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_validation_reset(self) -> None:
        """Test validation reset action."""
        # Arrange
        mock_validation_config = MagicMock()
        mock_validation_config.config = MagicMock()
        mock_validation_config.config.model_dump.return_value = {"enabled": True}
        mock_validation_config.reset_to_defaults = MagicMock()
        mock_validation_config.save = AsyncMock()
        mgrs = make_test_managers(validation_config=mock_validation_config)

        # Act
        result = await configure_validation(mgrs, "reset", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["message"] == "Configuration reset to defaults"
        mock_validation_config.reset_to_defaults.assert_called_once()
        mock_validation_config.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_validation_unknown_action(self) -> None:
        """Test validation with unknown action returns error."""
        # Arrange
        mock_validation_config = MagicMock()
        mgrs = make_test_managers(validation_config=mock_validation_config)

        # Act
        result = await configure_validation(mgrs, "unknown", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Unknown action" in result_data["error"]
        assert "valid_actions" in result_data

    @pytest.mark.asyncio
    async def test_handle_validation_update(self) -> None:
        """Test _handle_validation_update helper."""
        # Arrange
        mock_validation_config = MagicMock()
        mock_validation_config.config = MagicMock()
        mock_validation_config.config.model_dump.return_value = {"enabled": True}
        mock_validation_config.save = AsyncMock()

        # Act
        result = await handle_validation_update(
            mock_validation_config, {"enabled": True}, None, None
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        mock_validation_config.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_validation_reset(self) -> None:
        """Test _handle_validation_reset helper."""
        # Arrange
        mock_validation_config = MagicMock()
        mock_validation_config.config = MagicMock()
        mock_validation_config.config.model_dump.return_value = {"enabled": True}
        mock_validation_config.reset_to_defaults = MagicMock()
        mock_validation_config.save = AsyncMock()

        # Act
        result = await handle_validation_reset(mock_validation_config)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "reset to defaults" in result_data["message"]


class TestOptimizationConfiguration:
    """Test optimization configuration helpers."""

    @pytest.mark.asyncio
    async def test_configure_optimization_view(self) -> None:
        """Test optimization view action."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.to_dict.return_value = {
            "enabled": True,
            "token_budget": {"default_budget": 100000},
        }
        mgrs = make_test_managers(optimization_config=mock_optimization_config)

        # Act
        result = await configure_optimization(mgrs, "view", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["component"] == "optimization"

    @pytest.mark.asyncio
    async def test_configure_optimization_update_with_settings(self) -> None:
        """Test optimization update with settings dict."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.to_dict.return_value = {
            "enabled": True,
            "token_budget": {"default_budget": 90000},
        }
        mock_optimization_config.save_config = AsyncMock(return_value=True)
        mgrs = make_test_managers(optimization_config=mock_optimization_config)

        settings: dict[str, JsonValue] = {"token_budget.default_budget": 90000}

        # Act
        result = await configure_optimization(mgrs, "update", settings, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["message"] == "Configuration updated"
        mock_optimization_config.save_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_optimization_reset(self) -> None:
        """Test optimization reset action."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.to_dict.return_value = {"enabled": True}
        mock_optimization_config.reset = AsyncMock()
        mgrs = make_test_managers(optimization_config=mock_optimization_config)

        # Act
        result = await configure_optimization(mgrs, "reset", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["message"] == "Configuration reset to defaults"
        mock_optimization_config.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_optimization_unknown_action(self) -> None:
        """Test optimization with unknown action returns error."""
        # Arrange
        mock_optimization_config = MagicMock()
        mgrs = make_test_managers(optimization_config=mock_optimization_config)

        # Act
        result = await configure_optimization(mgrs, "unknown", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Unknown action" in result_data["error"]
        assert "valid_actions" in result_data

    @pytest.mark.asyncio
    async def test_handle_optimization_update(self) -> None:
        """Test _handle_optimization_update helper."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.to_dict.return_value = {"enabled": True}
        mock_optimization_config.save_config = AsyncMock(return_value=True)

        # Act
        result = await handle_optimization_update(
            mock_optimization_config, {"enabled": True}, None, None
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        mock_optimization_config.save_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_optimization_reset(self) -> None:
        """Test _handle_optimization_reset helper."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.to_dict.return_value = {"enabled": True}
        mock_optimization_config.reset = AsyncMock()

        # Act
        result = await handle_optimization_reset(mock_optimization_config)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "reset to defaults" in result_data["message"]


class TestLearningConfiguration:
    """Test learning configuration helpers."""

    @pytest.mark.asyncio
    async def test_configure_learning_view(self) -> None:
        """Test learning view action."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_learning_engine.data_manager.get_all_patterns.return_value = {}

        mock_optimization_config = MagicMock()
        mock_optimization_config.config = {"learning": {"enabled": True}}

        mgrs = make_test_managers(
            learning_engine=mock_learning_engine,
            optimization_config=mock_optimization_config,
        )

        # Act
        result = await configure_learning(mgrs, "view", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["component"] == "learning"
        assert "learned_patterns" in result_data

    @pytest.mark.asyncio
    async def test_configure_learning_update_with_settings(self) -> None:
        """Test learning update with settings dict."""
        # Arrange
        mock_learning_engine = MagicMock()

        mock_optimization_config = MagicMock()
        mock_optimization_config.config = {"learning": {"enabled": True}}
        mock_optimization_config.save_config = AsyncMock(return_value=True)

        mgrs = make_test_managers(
            learning_engine=mock_learning_engine,
            optimization_config=mock_optimization_config,
        )

        settings: dict[str, JsonValue] = {"learning.enabled": True}

        # Act
        result = await configure_learning(mgrs, "update", settings, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["message"] == "Configuration updated"

    @pytest.mark.asyncio
    async def test_configure_learning_update_export_patterns(self) -> None:
        """Test learning update with export_patterns key."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_pattern = MagicMock()
        mock_pattern.to_dict.return_value = {
            "pattern_id": "test",
            "confidence": 0.8,
        }
        mock_learning_engine.data_manager.get_all_patterns.return_value = {
            "test": mock_pattern
        }

        mock_optimization_config = MagicMock()
        mock_optimization_config.config = {"learning": {"enabled": True}}

        mgrs = make_test_managers(
            learning_engine=mock_learning_engine,
            optimization_config=mock_optimization_config,
        )

        # Act
        result = await configure_learning(mgrs, "update", None, "export_patterns", True)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["action"] == "export_patterns"
        assert "patterns" in result_data

    @pytest.mark.asyncio
    async def test_configure_learning_reset(self) -> None:
        """Test learning reset action."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_learning_engine.reset_learning_data = AsyncMock(return_value=True)

        mock_optimization_config = MagicMock()
        mock_optimization_config.config = {"learning": {"enabled": True}}
        mock_optimization_config.save_config = AsyncMock(return_value=True)

        mgrs = make_test_managers(
            learning_engine=mock_learning_engine,
            optimization_config=mock_optimization_config,
        )

        # Act
        result = await configure_learning(mgrs, "reset", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "reset to defaults" in result_data["message"]
        mock_learning_engine.reset_learning_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_learning_unknown_action(self) -> None:
        """Test learning with unknown action returns error."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_optimization_config = MagicMock()
        mock_optimization_config.config = {"learning": {"enabled": True}}

        mgrs = make_test_managers(
            learning_engine=mock_learning_engine,
            optimization_config=mock_optimization_config,
        )

        # Act
        result = await configure_learning(mgrs, "unknown", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Unknown action" in result_data["error"]
        assert "valid_actions" in result_data

    @pytest.mark.asyncio
    async def test_handle_learning_view(self) -> None:
        """Test _handle_learning_view helper."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_learning_engine.data_manager.get_all_patterns.return_value = {}

        mock_adaptation_config = MagicMock()
        mock_adaptation_config.to_dict.return_value = {"learning": {"enabled": True}}

        # Act
        result = handle_learning_view(mock_learning_engine, mock_adaptation_config)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["component"] == "learning"
        assert "learned_patterns" in result_data

    @pytest.mark.asyncio
    async def test_handle_learning_update(self) -> None:
        """Test _handle_learning_update helper."""
        # Arrange
        mock_learning_engine = MagicMock()

        mock_optimization_config = MagicMock()
        mock_optimization_config.save_config = AsyncMock(return_value=True)

        mock_adaptation_config = MagicMock()
        mock_adaptation_config.to_dict.return_value = {"learning": {"enabled": True}}

        # Act
        result = await handle_learning_update(
            mock_learning_engine,
            mock_optimization_config,
            mock_adaptation_config,
            {"learning.enabled": True},
            None,
            None,
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_handle_learning_reset(self) -> None:
        """Test _handle_learning_reset helper."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_learning_engine.reset_learning_data = AsyncMock(return_value=True)

        mock_optimization_config = MagicMock()
        mock_optimization_config.save_config = AsyncMock(return_value=True)

        mock_adaptation_config = MagicMock()
        mock_adaptation_config.to_dict.return_value = {"learning": {"enabled": True}}
        mock_adaptation_config.reset_to_defaults = MagicMock()

        # Act
        result = await handle_learning_reset(
            mock_learning_engine, mock_optimization_config, mock_adaptation_config
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "reset to defaults" in result_data["message"]


class TestHelperFunctions:
    """Test helper functions."""

    def test_apply_config_updates_with_settings(self) -> None:
        """Test applying config updates with settings dict."""
        # Arrange
        mock_config = MagicMock()
        settings: dict[str, JsonValue] = {"key1": "value1", "key2": "value2"}

        # Act
        result = apply_config_updates(mock_config, settings, None, None)

        # Assert
        assert result is None
        assert mock_config.set.call_count == 2

    def test_apply_config_updates_with_key_value(self) -> None:
        """Test applying config updates with key and value."""
        # Arrange
        mock_config = MagicMock()

        # Act
        result = apply_config_updates(mock_config, None, "test_key", "test_value")

        # Assert
        assert result is None
        mock_config.set.assert_called_once_with("test_key", "test_value")

    def test_apply_config_updates_missing_parameters(self) -> None:
        """Test applying config updates without required parameters returns error."""
        # Arrange
        mock_config = MagicMock()

        # Act
        result = apply_config_updates(mock_config, None, None, None)

        # Assert
        assert result is not None
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Either settings or key+value required" in result_data["error"]

    def test_apply_config_updates_key_without_value(self) -> None:
        """Test applying config updates with key but no value returns error."""
        # Arrange
        mock_config = MagicMock()

        # Act
        result = apply_config_updates(mock_config, None, "test_key", None)

        # Assert
        assert result is not None
        result_data = json.loads(result)
        assert result_data["status"] == "error"

    def test_create_success_response_with_message(self) -> None:
        """Test creating success response with message."""
        # Arrange
        component = "validation"
        configuration: ModelDict = {"enabled": True}
        message = "Test message"

        # Act
        result = create_success_response(component, configuration, message)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["component"] == component
        assert result_data["configuration"] == configuration
        assert result_data["message"] == message

    def test_create_success_response_without_message(self) -> None:
        """Test creating success response without message."""
        # Arrange
        component = "optimization"
        configuration: ModelDict = {"enabled": False}

        # Act
        result = create_success_response(component, configuration, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["component"] == component
        assert result_data["configuration"] == configuration
        assert "message" not in result_data

    def test_create_error_response(self) -> None:
        """Test creating error response."""
        # Arrange
        error = "Test error message"
        valid_actions: JsonValue = ["view", "update", "reset"]

        # Act
        result = create_error_response(error, valid_actions=valid_actions)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert result_data["error"] == error
        assert result_data["valid_actions"] == ["view", "update", "reset"]

    def test_get_learned_patterns(self) -> None:
        """Test getting learned patterns."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_pattern = MagicMock()
        mock_pattern.to_dict.return_value = {"pattern_id": "test", "confidence": 0.8}
        mock_learning_engine.data_manager.get_all_patterns.return_value = {
            "test": mock_pattern
        }

        # Act
        result = get_learned_patterns(mock_learning_engine)

        # Assert
        assert "test" in result.patterns
        test_pattern = result.patterns["test"].model_dump(mode="json")
        assert test_pattern["pattern_id"] == "test"
        assert test_pattern["confidence"] == 0.8

    def test_get_learned_patterns_empty(self) -> None:
        """Test getting learned patterns when empty."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_learning_engine.data_manager.get_all_patterns.return_value = {}

        # Act
        result = get_learned_patterns(mock_learning_engine)

        # Assert
        assert result.patterns == {}

    def test_export_learned_patterns(self) -> None:
        """Test exporting learned patterns."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_pattern = MagicMock()
        mock_pattern.to_dict.return_value = {
            "pattern_id": "test",
            "confidence": 0.9,
        }
        mock_learning_engine.data_manager.get_all_patterns.return_value = {
            "test": mock_pattern
        }

        # Act
        result = export_learned_patterns(mock_learning_engine)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["component"] == "learning"
        assert result_data["action"] == "export_patterns"
        assert "patterns" in result_data
        assert "test" in result_data["patterns"]


class TestEdgeCases:
    """Test edge cases and error paths."""

    @pytest.mark.asyncio
    async def test_configure_validation_update_error_handling(self) -> None:
        """Test validation update handles errors from apply_config_updates."""
        # Arrange
        mock_validation_config = MagicMock()
        mgrs = make_test_managers(validation_config=mock_validation_config)

        # Act - no settings or key/value provided
        result = await configure_validation(mgrs, "update", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Either settings or key+value required" in result_data["error"]

    @pytest.mark.asyncio
    async def test_configure_optimization_update_error_handling(self) -> None:
        """Test optimization update handles errors from apply_config_updates."""
        # Arrange
        mock_optimization_config = MagicMock()
        mgrs = make_test_managers(optimization_config=mock_optimization_config)

        # Act - no settings or key/value provided
        result = await configure_optimization(mgrs, "update", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Either settings or key+value required" in result_data["error"]

    @pytest.mark.asyncio
    async def test_configure_learning_update_error_handling(self) -> None:
        """Test learning update handles errors from apply_config_updates."""
        # Arrange
        mock_learning_engine = MagicMock()
        mock_optimization_config = MagicMock()
        mock_optimization_config.config = {"learning": {"enabled": True}}
        mgrs = make_test_managers(
            learning_engine=mock_learning_engine,
            optimization_config=mock_optimization_config,
        )

        # Act - no settings or key/value provided
        result = await configure_learning(mgrs, "update", None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Either settings or key+value required" in result_data["error"]
