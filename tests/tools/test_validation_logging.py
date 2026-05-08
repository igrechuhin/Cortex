"""Split from test_validation_operations.py to keep file size under limits."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.validation.operations import (
    validate_impl as _validate_impl,
)


class TestValidateContextLogging:
    """Test validate tool Context logging (FastMCP)."""

    @pytest.mark.asyncio
    async def test_validate_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, validate logs start and completion via log_client."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.validation.operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.validation.dispatch.prepare_validation_managers",
                new_callable=AsyncMock,
            ) as mock_prepare,
            patch(
                "cortex.tools.validation.dispatch.call_dispatch_validation",
                new_callable=AsyncMock,
                return_value='{"status": "success"}',
            ),
        ):
            mock_prepare.return_value = (tmp_path, {})

            # Act
            result = await _validate_impl(
                check_type="schema",
                ctx=mock_ctx,
            )

            # Assert
            assert json.loads(result)["status"] == "success"
            args_list = [c[0] for c in mock_log.call_args_list]
            levels_and_messages = [(a[1], a[2]) for a in args_list]
            assert ("info", "validate: starting") in levels_and_messages
            assert ("info", "validate: completed") in levels_and_messages

    @pytest.mark.asyncio
    async def test_validate_calls_log_client_warning_on_invalid_check_type_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When check_type is invalid and ctx is passed, validate logs warning."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        mock_ctx = AsyncMock()
        with patch(
            "cortex.tools.validation.operations.log_client",
            new_callable=AsyncMock,
        ) as mock_log:
            # Act
            result = await _validate_impl(
                check_type="invalid",  # type: ignore[arg-type]
                ctx=mock_ctx,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert any(
                c[0][1] == "warning" and c[0][2] == "validate: invalid check_type"
                for c in mock_log.call_args_list
                if len(c[0]) >= 3
            )

    @pytest.mark.asyncio
    async def test_validate_calls_log_client_error_on_exception_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When validation raises and ctx is passed, validate logs error."""
        # Arrange
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.validation.operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.validation.operations.prepare_validation_managers",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Setup failed"),
            ),
        ):
            # Act
            result = await _validate_impl(
                check_type="schema",
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
            assert "validate: failed" in error_calls[0][2]
