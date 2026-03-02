"""Tests for configuration operations module."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import JsonValue, ModelDict
from cortex.tools.config import ConfigAction, get_config_resource
from cortex.tools.config.operations import (
    apply_config_updates,
    configure,
    configure_learning,
    configure_optimization,
    configure_validation,
    create_configuration_exception_error,
    create_error_response,
    create_invalid_component_error,
    create_success_response,
    export_learned_patterns,
    get_component_handler,
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


@pytest.fixture(autouse=True)
def _skip_usage_context_init():  # pyright: ignore[reportUnusedFunction]
    """Avoid slow resolve_project_root + get_managers in ensure_usage_context."""
    with patch("cortex.core.mcp_stability_usage.get_current_managers", return_value={}):
        yield


@pytest.mark.timeout(10)
class TestConfigureMainHandler:
    """Test main configure handler."""

    @pytest.mark.asyncio
    async def test_configure_validation_view(self, tmp_path: Path) -> None:
        """Test viewing validation configuration."""
        # Arrange
        with patch("cortex.tools.config.operations.get_managers") as mock_get_managers:
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
            with patch(
                "cortex.tools.config.operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ):
                result = await configure(
                    component="validation",
                    action="view",
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
        with patch("cortex.tools.config.operations.get_managers") as mock_get_managers:
            mock_optimization_config = MagicMock()
            mock_optimization_config.to_dict.return_value = {
                "enabled": True,
                "token_budget": {"default_budget": 100000},
            }
            mock_get_managers.return_value = make_test_managers(
                optimization_config=mock_optimization_config
            )

            # Act
            with patch(
                "cortex.tools.config.operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ):
                result = await configure(
                    component="optimization",
                    action="view",
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
        with patch("cortex.tools.config.operations.get_managers") as mock_get_managers:
            mock_learning_engine = MagicMock()
            mock_learning_engine.data_manager.get_all_patterns.return_value = {}

            mock_optimization_config = MagicMock()
            mock_optimization_config.config = {"learning": {"enabled": True}}

            mock_get_managers.return_value = make_test_managers(
                learning_engine=mock_learning_engine,
                optimization_config=mock_optimization_config,
            )

            # Act
            with patch(
                "cortex.tools.config.operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ):
                result = await configure(
                    component="learning",
                    action="view",
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
        with patch("cortex.tools.config.operations.get_managers") as mock_get_managers:
            mock_get_managers.return_value = {}

            # Act
            with patch(
                "cortex.tools.config.operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ):
                result = await configure(
                    component="unknown",  # type: ignore[arg-type]
                    action="view",
                )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Invalid component" in result_data["error"]
            assert "available_options" in result_data
            assert "suggestion" in result_data

    @pytest.mark.asyncio
    async def test_configure_exception_handling(self, tmp_path: Path) -> None:
        """Test configure handles exceptions gracefully."""
        # Arrange
        with patch("cortex.tools.config.operations.get_managers") as mock_get_managers:
            mock_get_managers.side_effect = RuntimeError("Test error")

            # Act
            with patch(
                "cortex.tools.config.operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ):
                result = await configure(
                    component="validation",
                    action="view",
                )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Test error" in result_data["error"]
            assert result_data["error_type"] == "RuntimeError"


@pytest.mark.timeout(10)
class TestGetConfigResourceAndUpdateConfig:
    """Test get_config_resource (Phase 43 Resource) and update_config (Phase 43 Tool)."""

    @pytest.mark.asyncio
    async def test_get_config_resource_validation_returns_success(self) -> None:
        """Test get_config_resource returns view result for validation component."""
        # Arrange
        with patch("cortex.tools.config.hybrid.get_managers") as mock_get_managers:
            mock_validation_config = MagicMock()
            mock_validation_config.config = MagicMock()
            mock_validation_config.config.model_dump.return_value = {
                "enabled": True,
                "strict_mode": False,
            }
            mock_get_managers.return_value = make_test_managers(
                validation_config=mock_validation_config
            )
            with patch(
                "cortex.tools.config.hybrid.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result = await get_config_resource(component="validation")

                # Assert
                result_data = json.loads(result)
                assert result_data["status"] == "success"
                assert result_data["component"] == "validation"
                assert "configuration" in result_data

    @pytest.mark.asyncio
    async def test_get_config_resource_optimization_returns_success(self) -> None:
        """Test get_config_resource returns view result for optimization component."""
        # Arrange
        with patch("cortex.tools.config.hybrid.get_managers") as mock_get_managers:
            mock_optimization_config = MagicMock()
            mock_optimization_config.to_dict.return_value = {
                "enabled": True,
                "token_budget": {"default_budget": 100000},
            }
            mock_get_managers.return_value = make_test_managers(
                optimization_config=mock_optimization_config
            )
            with patch(
                "cortex.tools.config.hybrid.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result = await get_config_resource(component="optimization")

                # Assert
                result_data = json.loads(result)
                assert result_data["status"] == "success"
                assert result_data["component"] == "optimization"
                assert "configuration" in result_data

    @pytest.mark.asyncio
    async def test_get_config_resource_learning_returns_success(self) -> None:
        """Test get_config_resource returns view result for learning component."""
        # Arrange
        with patch("cortex.tools.config.hybrid.get_managers") as mock_get_managers:
            mock_learning_engine = MagicMock()
            mock_learning_engine.data_manager.get_all_patterns.return_value = {}

            mock_optimization_config = MagicMock()
            mock_optimization_config.config = {"learning": {"enabled": True}}

            mock_get_managers.return_value = make_test_managers(
                learning_engine=mock_learning_engine,
                optimization_config=mock_optimization_config,
            )
            with patch(
                "cortex.tools.config.hybrid.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                # Act
                result = await get_config_resource(component="learning")

                # Assert
                result_data = json.loads(result)
                assert result_data["status"] == "success"
                assert result_data["component"] == "learning"
                assert "configuration" in result_data
                assert "learned_patterns" in result_data

    @pytest.mark.asyncio
    async def test_get_config_resource_unknown_component_returns_error(self) -> None:
        """Test get_config_resource with unknown component returns error."""
        with patch(
            "cortex.tools.config.hybrid.get_managers",
            return_value=make_test_managers(),
        ):
            with patch(
                "cortex.tools.config.hybrid.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ):
                result = await get_config_resource(component="unknown")
                result_data = json.loads(result)
                assert result_data["status"] == "error"
                assert "Invalid component" in result_data["error"]
                assert "available_options" in result_data


@pytest.mark.timeout(10)
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
        result = await configure_validation(mgrs, ConfigAction.VIEW, None, None, None)

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
            ConfigAction.UPDATE,
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
        result = await configure_validation(
            mgrs, ConfigAction.UPDATE, None, "strict_mode", True
        )

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
        result = await configure_validation(mgrs, ConfigAction.RESET, None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["message"] == "Configuration reset to defaults"
        mock_validation_config.reset_to_defaults.assert_called_once()
        mock_validation_config.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_validation_unknown_action(self) -> None:
        """Test validation with unknown action returns error."""
        # Act: invalid action is rejected at configure() boundary before handler
        result = await configure("validation", "unknown")

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid action" in result_data["error"]
        assert "available_options" in result_data
        assert "suggestion" in result_data

    @pytest.mark.asyncio
    async def test_configure_validation_invalid_action_else_branch(self) -> None:
        """Test validation handler else branch for non-VIEW/UPDATE/RESET action."""
        mgrs = make_test_managers(validation_config=MagicMock())
        fake_action = cast(ConfigAction, type("FakeAction", (), {"value": "other"})())

        result = await configure_validation(mgrs, fake_action, None, None, None)

        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "action" in result_data.get("error", "").lower() or "action" in str(
            result_data
        )

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


@pytest.mark.timeout(10)
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
        result = await configure_optimization(mgrs, ConfigAction.VIEW, None, None, None)

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
        result = await configure_optimization(
            mgrs, ConfigAction.UPDATE, settings, None, None
        )

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
        result = await configure_optimization(
            mgrs, ConfigAction.RESET, None, None, None
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["message"] == "Configuration reset to defaults"
        mock_optimization_config.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_optimization_unknown_action(self) -> None:
        """Test optimization with unknown action returns error."""
        # Act: invalid action is rejected at configure() boundary before handler
        result = await configure("optimization", "unknown")

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid action" in result_data["error"]
        assert "available_options" in result_data
        assert "suggestion" in result_data

    @pytest.mark.asyncio
    async def test_configure_optimization_invalid_action_else_branch(self) -> None:
        """Test optimization handler else branch for non-VIEW/UPDATE/RESET action."""
        mgrs = make_test_managers(optimization_config=MagicMock())
        fake_action = cast(ConfigAction, type("FakeAction", (), {"value": "other"})())

        result = await configure_optimization(mgrs, fake_action, None, None, None)

        result_data = json.loads(result)
        assert result_data["status"] == "error"

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


@pytest.mark.timeout(10)
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
        result = await configure_learning(mgrs, ConfigAction.VIEW, None, None, None)

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
        result = await configure_learning(
            mgrs, ConfigAction.UPDATE, settings, None, None
        )

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
        result = await configure_learning(
            mgrs, ConfigAction.UPDATE, None, "export_patterns", True
        )

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
        result = await configure_learning(mgrs, ConfigAction.RESET, None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert "reset to defaults" in result_data["message"]
        mock_learning_engine.reset_learning_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_learning_unknown_action(self) -> None:
        """Test learning with unknown action returns error."""
        # Act: invalid action is rejected at configure() boundary before handler
        result = await configure("learning", "unknown")

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid action" in result_data["error"]
        assert "available_options" in result_data
        assert "suggestion" in result_data

    @pytest.mark.asyncio
    async def test_configure_learning_invalid_action_else_branch(self) -> None:
        """Test learning handler else branch for non-VIEW/UPDATE/RESET action."""
        mock_optimization_config = MagicMock()
        mock_optimization_config.config = MagicMock()
        mgrs = make_test_managers(
            learning_engine=MagicMock(),
            optimization_config=mock_optimization_config,
        )
        fake_action = cast(ConfigAction, type("FakeAction", (), {"value": "other"})())

        result = await configure_learning(mgrs, fake_action, None, None, None)

        result_data = json.loads(result)
        assert result_data["status"] == "error"

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
        assert result_data["available_options"] == ["view", "update", "reset"]
        assert "suggestion" in result_data

    def test_create_error_response_unknown_component_branch(self) -> None:
        """create_error_response with 'Unknown component' uses valid_components suggestion."""
        error = "Unknown component: xyz"
        valid_components: JsonValue = ["validation", "optimization", "learning"]
        result_str: str = create_error_response(
            error, valid_components=valid_components
        )
        result_data = json.loads(result_str)
        assert result_data["status"] == "error"
        assert "Use one of the valid components" in result_data.get("suggestion", "")
        assert result_data["available_options"] == valid_components

    def test_create_error_response_unknown_action_branch(self) -> None:
        """create_error_response with 'Unknown action' uses valid_actions suggestion."""
        error = "Unknown action: bad_action"
        valid_actions: JsonValue = ["view", "update", "reset"]
        result_str: str = create_error_response(error, valid_actions=valid_actions)
        result_data = json.loads(result_str)
        assert result_data["status"] == "error"
        assert "Use one of the valid actions" in result_data.get("suggestion", "")
        assert result_data["available_options"] == valid_actions

    def test_create_error_response_example_component(self) -> None:
        """create_error_response with 'component' in error builds component example."""
        error = "Invalid component"
        valid_components: JsonValue = ["validation", "optimization"]
        result_str: str = create_error_response(
            error, valid_components=valid_components
        )
        result_data = json.loads(result_str)
        assert result_data["status"] == "error"
        assert result_data.get("example") == {
            "component": "validation",
            "action": "view",
        }

    def test_create_error_response_example_action(self) -> None:
        """create_error_response with 'action' in error builds action example."""
        error = "Invalid action"
        valid_actions: JsonValue = ["view", "update"]
        result_str: str = create_error_response(error, valid_actions=valid_actions)
        result_data = json.loads(result_str)
        assert result_data["status"] == "error"
        assert result_data.get("example") == {"action": "view"}

    def test_create_error_response_valid_operations_extracted(self) -> None:
        """create_error_response extracts available_options from valid_operations."""
        error = "Invalid operation"
        valid_operations: JsonValue = ["read", "write"]
        result_str: str = create_error_response(
            error, valid_operations=valid_operations
        )
        result_data = json.loads(result_str)
        assert result_data["status"] == "error"
        assert result_data["available_options"] == ["read", "write"]

    def test_create_error_response_empty_valid_components(self) -> None:
        """create_error_response with empty valid_components uses default in suggestion."""
        error = "Unknown component: x"
        valid_components: JsonValue = []
        result_str: str = create_error_response(
            error, valid_components=valid_components
        )
        result_data = json.loads(result_str)
        assert result_data["status"] == "error"
        assert "validation" in result_data.get("suggestion", "")

    def test_create_error_response_context_dict_passthrough(self) -> None:
        """create_error_response passes dict context through."""
        error = "Some error"
        context: JsonValue = {"key": "value"}
        result_str: str = create_error_response(error, context=context)
        result_data = json.loads(result_str)
        assert result_data["status"] == "error"
        assert result_data.get("context") == {"key": "value"}

    def test_create_error_response_context_non_dict_wrapped(self) -> None:
        """create_error_response wraps non-dict context in {'context': value}."""
        error = "Some error"
        context: JsonValue = "plain string"
        result_str: str = create_error_response(error, context=context)
        result_data = json.loads(result_str)
        assert result_data["status"] == "error"
        assert result_data.get("context") == {"context": "plain string"}

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
        result = await configure_validation(mgrs, ConfigAction.UPDATE, None, None, None)

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
        result = await configure_optimization(
            mgrs, ConfigAction.UPDATE, None, None, None
        )

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
        result = await configure_learning(mgrs, ConfigAction.UPDATE, None, None, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Either settings or key+value required" in result_data["error"]


@pytest.mark.timeout(10)
class TestConfigureContextLogging:
    """Test configure tool Context logging (FastMCP)."""

    @pytest.mark.asyncio
    async def test_configure_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, configure logs start and completion via log_client."""
        # Arrange
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.config.operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.config.operations.get_managers",
                new_callable=AsyncMock,
            ) as mock_get_managers,
        ):
            mock_get_managers.return_value = make_test_managers(
                validation_config=MagicMock(
                    config=MagicMock(
                        model_dump=MagicMock(
                            return_value={"enabled": True, "strict_mode": False}
                        )
                    )
                )
            )

            # Act
            with patch(
                "cortex.tools.config.operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ):
                result = await configure(
                    component="validation",
                    action="view",
                    ctx=mock_ctx,
                )

            # Assert
            assert json.loads(result)["status"] == "success"
            args_list = [c[0] for c in mock_log.call_args_list]
            levels_and_messages = [(a[1], a[2]) for a in args_list]
            assert ("info", "configure: starting") in levels_and_messages
            assert ("info", "configure: completed") in levels_and_messages

    @pytest.mark.asyncio
    async def test_configure_calls_log_client_warning_on_invalid_action_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When action is invalid and ctx is passed, configure logs warning."""
        # Arrange
        mock_ctx = AsyncMock()
        with patch(
            "cortex.tools.config.operations.log_client",
            new_callable=AsyncMock,
        ) as mock_log:
            # Act
            result = await configure(
                component="validation",
                action="invalid",  # type: ignore[arg-type]
                ctx=mock_ctx,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert any(
                c[0][1] == "warning" and c[0][2] == "configure: invalid action"
                for c in mock_log.call_args_list
                if len(c[0]) >= 3
            )

    @pytest.mark.asyncio
    async def test_configure_calls_log_client_warning_on_invalid_component_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When component is invalid and ctx is passed, configure logs warning."""
        # Arrange
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.config.operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.config.operations.get_managers",
                new_callable=AsyncMock,
            ) as mock_get_managers,
        ):
            mock_get_managers.return_value = make_test_managers()

            # Act
            result = await configure(
                component="unknown",
                action="view",
                ctx=mock_ctx,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert any(
                c[0][1] == "warning" and c[0][2] == "configure: invalid component"
                for c in mock_log.call_args_list
                if len(c[0]) >= 3
            )

    @pytest.mark.asyncio
    async def test_configure_calls_log_client_error_on_exception_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When configuration raises and ctx is passed, configure logs error."""
        # Arrange
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.config.operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.config.operations.get_managers",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Setup failed"),
            ),
        ):
            # Act
            result = await configure(
                component="validation",
                action="view",
                ctx=mock_ctx,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Setup failed" in result_data["error"]
            error_calls = [
                c[0]
                for c in mock_log.call_args_list
                if len(c[0]) >= 2 and c[0][1] == "error"
            ]
            assert len(error_calls) == 1


@pytest.mark.timeout(5)
class TestGetComponentHandlerAndErrorBuilders:
    """Unit tests for get_component_handler and error response builders."""

    def test_get_component_handler_returns_handler_for_validation(self) -> None:
        """get_component_handler('validation') returns configure_validation."""
        handler = get_component_handler("validation")
        assert handler is not None
        assert callable(handler)

    def test_get_component_handler_returns_handler_for_optimization(self) -> None:
        """get_component_handler('optimization') returns configure_optimization."""
        handler = get_component_handler("optimization")
        assert handler is not None
        assert callable(handler)

    def test_get_component_handler_returns_handler_for_learning(self) -> None:
        """get_component_handler('learning') returns configure_learning."""
        handler = get_component_handler("learning")
        assert handler is not None
        assert callable(handler)

    def test_get_component_handler_returns_none_for_unknown(self) -> None:
        """get_component_handler returns None for unknown component."""
        assert get_component_handler("unknown") is None
        assert get_component_handler("") is None

    def test_create_invalid_component_error_includes_valid_options(self) -> None:
        """create_invalid_component_error returns JSON with valid options."""
        result_str: str = create_invalid_component_error("bad_component")
        data = json.loads(result_str)
        assert data["status"] == "error"
        assert "bad_component" in result_str
        assert "validation" in result_str and "optimization" in result_str

    def test_create_configuration_exception_error_includes_message(self) -> None:
        """create_configuration_exception_error returns JSON with exception details."""
        exc = ValueError("Invalid value")
        result_str: str = create_configuration_exception_error(
            exc, component="validation", action="view"
        )
        data = json.loads(result_str)
        assert data["status"] == "error"
        assert "Invalid value" in result_str
