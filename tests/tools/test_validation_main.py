"""Split from test_validation_operations.py to keep file size under limits."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.validation.dispatch import (
    handle_infrastructure_validation_wrapper,
    handle_timestamps_validation_wrapper,
    setup_validation_managers,
)
from cortex.tools.validation.operations import (
    validate_impl as _validate_impl,
)
from tests.tools.validation_operations_support import (
    setup_validation_managers_mock_values,
)


class TestSetupValidationManagers:
    """Test setup validation managers helper."""

    @pytest.mark.asyncio
    async def test_setup_validation_managers_success(self, tmp_path: Path) -> None:
        """Test successful setup of validation managers."""
        mock_fs, manager_sequence = setup_validation_managers_mock_values()

        with (
            patch(
                "cortex.tools.validation.dispatch.initialization.get_managers"
            ) as mock_get_managers,
            patch("cortex.tools.validation.dispatch.get_manager") as mock_get_manager,
        ):
            mock_get_managers.return_value = {
                "fs": mock_fs,
                "index": manager_sequence[1],
            }
            mock_get_manager.side_effect = manager_sequence

            # Act
            result = await setup_validation_managers(tmp_path)

            # Assert
            assert "fs_manager" in result
            assert "metadata_index" in result
            assert "schema_validator" in result
            assert "duplication_detector" in result
            assert "quality_metrics" in result
            assert "validation_config" in result
            assert result["fs_manager"] == mock_fs
            assert result["metadata_index"] == manager_sequence[1]


class TestValidateMainFunction:
    """Test main validate function."""

    @pytest.mark.asyncio
    async def test_validate_schema_check(self, tmp_path: Path) -> None:
        """Test validate function with schema check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.operations.prepare_validation_managers"
            ) as mock_prepare,
            patch(
                "cortex.tools.validation.operations.call_dispatch_validation"
            ) as mock_dispatch,
        ):
            mock_prepare.return_value = (tmp_path, {})
            mock_dispatch.return_value = json.dumps({"status": "success"})

            # Act
            result = await _validate_impl(check_type="schema")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            mock_dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_duplications_check(self, tmp_path: Path) -> None:
        """Test validate function with duplications check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.dispatch.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation.dispatch.handle_duplications_validation_wrapper"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps({"status": "success"})

            # Act
            result = await _validate_impl(check_type="duplications")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_quality_check(self, tmp_path: Path) -> None:
        """Test validate function with quality check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.dispatch.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation.dispatch.handle_quality_validation_wrapper"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps({"status": "success"})

            # Act
            result = await _validate_impl(check_type="quality")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_infrastructure_check(self, tmp_path: Path) -> None:
        """Test validate function with infrastructure check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.dispatch.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation.dispatch.handle_infrastructure_validation_wrapper"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps(
                {
                    "status": "success",
                    "check_type": "infrastructure",
                    "checks_performed": {
                        "commit_ci_alignment": True,
                        "code_quality_consistency": True,
                    },
                    "issues_found": [],
                    "recommendations": [],
                }
            )

            # Act
            result = await _validate_impl(
                check_type="infrastructure",  # type: ignore[arg-type]
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["check_type"] == "infrastructure"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_infrastructure_validation_wrapper_calls_impl(
        self, tmp_path: Path
    ) -> None:
        """Wrapper delegates to handle_infrastructure_validation (covers dispatch)."""
        with patch(
            "cortex.tools.validation.dispatch.handle_infrastructure_validation",
            new_callable=AsyncMock,
            return_value='{"status":"success","checks_performed":{}}',
        ) as mock_impl:
            result = await handle_infrastructure_validation_wrapper(
                tmp_path, False, False, False, False
            )
            mock_impl.assert_called_once_with(tmp_path, False, False, False, False)
            assert "status" in result

    @pytest.mark.asyncio
    async def test_handle_timestamps_validation_wrapper_calls_impl(
        self, tmp_path: Path
    ) -> None:
        """Wrapper delegates to handle_timestamps_validation (covers dispatch)."""
        mock_fs = MagicMock()
        managers: dict[str, Any] = {"fs_manager": mock_fs}
        with patch(
            "cortex.tools.validation.dispatch.handle_timestamps_validation",
            new_callable=AsyncMock,
            return_value='{"status":"success","issues":[]}',
        ) as mock_impl:
            result = await handle_timestamps_validation_wrapper(
                managers, tmp_path, None
            )
            mock_impl.assert_called_once_with(mock_fs, tmp_path, None)
            assert "status" in result

    @pytest.mark.asyncio
    async def test_validate_invalid_check_type(self, tmp_path: Path) -> None:
        """Test validate function with invalid check type."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with patch(
            "cortex.tools.validation.dispatch.setup_validation_managers"
        ) as mock_setup:
            mock_setup.return_value = {}

            # Act
            result = await _validate_impl(
                check_type="invalid",  # type: ignore[arg-type]
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Invalid check_type" in result_data["error"]

    @pytest.mark.asyncio
    async def test_validate_exception_handling(self, tmp_path: Path) -> None:
        """Test validate function exception handling."""
        # Arrange
        with patch(
            "cortex.tools.validation.dispatch.setup_validation_managers"
        ) as mock_setup:
            mock_setup.side_effect = RuntimeError("Setup failed")

            # Act
            result = await _validate_impl(check_type="schema")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Setup failed" in result_data["error"]
            assert result_data["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_validate_with_all_parameters(self, tmp_path: Path) -> None:
        """Test validate function with all optional parameters."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)

        with (
            patch(
                "cortex.tools.validation.dispatch.setup_validation_managers"
            ) as mock_setup,
            patch(
                "cortex.tools.validation.dispatch.handle_duplications_validation_wrapper"
            ) as mock_handle,
        ):
            mock_setup.return_value = {}
            mock_handle.return_value = json.dumps(
                {"status": "success", "threshold": 0.9, "suggested_fixes": []}
            )

            # Act
            result = await _validate_impl(
                check_type="duplications",
                file_name="test.md",
                strict_mode=True,
                similarity_threshold=0.9,
                suggest_fixes=False,
                response_format="detailed",
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["threshold"] == 0.9
