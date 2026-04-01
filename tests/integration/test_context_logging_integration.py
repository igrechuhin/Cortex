"""
Integration tests for FastMCP Context logging.

These tests verify that MCP tools correctly use Context logging to send
messages to clients via the MCP protocol, and that logs appear correctly
in client responses.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.context_logging import log_client, report_progress_safe
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.files.operations import manage_file
from cortex.tools.validation.operations import validate_impl as validate


def _create_memory_bank_file(project_root: Path, name: str, content: str) -> Path:
    """Create a file in the memory bank directory."""
    mb_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    mb_dir.mkdir(parents=True, exist_ok=True)
    f = mb_dir / name
    _ = f.write_text(content)
    return f


def _extract_log_args(mock_log: AsyncMock) -> list[tuple[object, ...]]:
    """Extract positional arg tuples from mock_log call list."""
    return [c[0] for c in mock_log.call_args_list]


def _assert_has_log_keyword(
    call_args_list: list[tuple[object, ...]], keyword: str
) -> None:
    """Assert at least one log call has keyword in message (arg index 2)."""
    matches = [
        args
        for args in call_args_list
        if len(args) >= 3 and keyword in str(args[2]).lower()
    ]
    assert len(matches) > 0, f"No log with '{keyword}' found"


def _manage_file_patches(project_root: Path, mock_log: AsyncMock):
    """Return a combined context manager patching manage_file helpers."""
    resolve_mock = AsyncMock(return_value=project_root)
    from contextlib import contextmanager

    @contextmanager
    def _combined():
        with (
            patch(
                "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
                resolve_mock,
            ),
            patch("cortex.tools.files.crud_operations.log_client", mock_log),
            patch("cortex.tools.files.manage_file_helpers.log_client", mock_log),
        ):
            yield

    return _combined()


@pytest.mark.asyncio
class TestContextLoggingIntegration:
    """Integration tests for Context logging in MCP tools."""

    async def test_manage_file_logs_to_context_when_ctx_provided(
        self, temp_project_root: Path, mock_ctx: AsyncMock
    ) -> None:
        """Test that manage_file logs to Context when ctx is provided."""
        _ = _create_memory_bank_file(temp_project_root, "test.md", "# Test\n\nContent")
        mock_log = AsyncMock()

        with _manage_file_patches(temp_project_root, mock_log):
            result_str = await manage_file(
                file_name="test.md", operation="read", ctx=mock_ctx
            )
            result = json.loads(result_str)

        assert result["status"] == "success"
        assert mock_log.call_count >= 2
        call_args = _extract_log_args(mock_log)
        _assert_has_log_keyword(call_args, "starting")
        _assert_has_log_keyword(call_args, "completed")

    async def test_validate_logs_to_context_when_ctx_provided(
        self, temp_project_root: Path, mock_ctx: AsyncMock
    ) -> None:
        """Test that validate logs to Context when ctx is provided."""
        _ = _create_memory_bank_file(
            temp_project_root,
            "projectBrief.md",
            "# Project Brief\n\n## Overview\n\nTest",
        )
        resolve_mock = AsyncMock(return_value=temp_project_root)

        with (
            patch(
                "cortex.tools.validation.operations.resolve_project_root_async",
                resolve_mock,
            ),
            patch(
                "cortex.tools.validation.operations.log_client", new_callable=AsyncMock
            ) as mock_log,
        ):
            result_str = await validate(
                check_type="schema", file_name="projectBrief.md", ctx=mock_ctx
            )
            result = json.loads(result_str)

        assert result["status"] == "success"
        assert mock_log.call_count >= 2
        _assert_has_log_keyword(_extract_log_args(mock_log), "starting")

    async def test_error_logging_when_tool_fails(
        self, temp_project_root: Path, mock_ctx: AsyncMock
    ) -> None:
        """Test that error logging occurs when a tool fails."""
        mb_dir = get_cortex_path(temp_project_root, CortexResourceType.MEMORY_BANK)
        mb_dir.mkdir(parents=True, exist_ok=True)
        mock_log = AsyncMock()

        with _manage_file_patches(temp_project_root, mock_log):
            result_str = await manage_file(
                file_name="nonexistent.md", operation="read", ctx=mock_ctx
            )
            result = json.loads(result_str)

        assert result["status"] == "error"
        call_args = _extract_log_args(mock_log)
        error_logs = [
            args for args in call_args if len(args) >= 2 and args[1] == "error"
        ]
        assert len(error_logs) > 0

    async def test_progress_reporting_in_long_operations(
        self, mock_ctx: AsyncMock
    ) -> None:
        """Test that progress reporting works for long-running operations."""
        # Arrange
        progress_calls: list[tuple[float, float | None]] = []

        async def capture_progress(p: float, t: float | None = None) -> None:
            progress_calls.append((p, t))

        mock_ctx.report_progress = AsyncMock(side_effect=capture_progress)

        # Act - Simulate a long-running operation
        await report_progress_safe(mock_ctx, 25, 100)
        await report_progress_safe(mock_ctx, 50, 100)
        await report_progress_safe(mock_ctx, 75, 100)
        await report_progress_safe(mock_ctx, 100, 100)

        # Assert
        assert len(progress_calls) == 4
        assert progress_calls[0] == (25, 100)
        assert progress_calls[1] == (50, 100)
        assert progress_calls[2] == (75, 100)
        assert progress_calls[3] == (100, 100)

    async def test_log_client_falls_back_to_standard_logger_when_ctx_none(
        self,
    ) -> None:
        """Test that log_client falls back to standard logger when ctx is None."""
        # Arrange
        with patch("cortex.core.context_logging.logger") as mock_logger:
            # Act
            await log_client(None, "info", "test message")

            # Assert
            mock_logger.info.assert_called_once_with("test message")

    async def test_log_client_handles_connection_errors_gracefully(
        self, mock_ctx: AsyncMock
    ) -> None:
        """Test that log_client handles connection errors without raising."""
        # Arrange
        import anyio

        mock_ctx.log = AsyncMock(side_effect=anyio.BrokenResourceError())

        with patch("cortex.core.context_logging.logger") as mock_logger:
            # Act - Should not raise
            await log_client(mock_ctx, "info", "test message")

            # Assert - Should log debug message about connection closed
            mock_logger.debug.assert_called_once()
            debug_call = mock_logger.debug.call_args[0][0]
            assert "connection closed" in debug_call.lower()

    async def test_report_progress_safe_handles_connection_errors_gracefully(
        self, mock_ctx: AsyncMock
    ) -> None:
        """Test that report_progress_safe handles connection errors without raising."""
        # Arrange
        import anyio

        mock_ctx.report_progress = AsyncMock(side_effect=anyio.BrokenResourceError())

        with patch("cortex.core.context_logging.logger") as mock_logger:
            # Act - Should not raise
            await report_progress_safe(mock_ctx, 50, 100)

            # Assert - Should log debug message about connection closed
            mock_logger.debug.assert_called_once()
            debug_call = mock_logger.debug.call_args[0][0]
            assert "connection closed" in debug_call.lower()

    async def test_all_log_levels_work_correctly(self, mock_ctx: AsyncMock) -> None:
        """Test that all log levels (debug, info, warning, error) work correctly."""
        # Arrange
        log_calls: list[tuple[str, str]] = []

        async def capture_log(level: str, message: str, **kwargs: object) -> None:
            log_calls.append((level, message))

        mock_ctx.log = AsyncMock(side_effect=capture_log)

        # Act
        await log_client(mock_ctx, "debug", "debug message")
        await log_client(mock_ctx, "info", "info message")
        await log_client(mock_ctx, "warning", "warning message")
        await log_client(mock_ctx, "error", "error message")

        # Assert
        assert len(log_calls) == 4
        assert log_calls[0] == ("debug", "debug message")
        assert log_calls[1] == ("info", "info message")
        assert log_calls[2] == ("warning", "warning message")
        assert log_calls[3] == ("error", "error message")
