"""Unit tests for context_logging module."""

from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.context_logging import log_client, report_progress_safe

_CONTEXT_LOGGING_LOGGER = "cortex.core.context_logging"


@pytest.mark.asyncio
async def test_log_client_when_ctx_none_uses_logger() -> None:
    """When ctx is None, log_client logs to standard logger."""
    with patch(f"{_CONTEXT_LOGGING_LOGGER}.logger") as mock_logger:
        await log_client(None, "info", "test message")
        mock_logger.info.assert_called_once_with("test message")


@pytest.mark.asyncio
async def test_log_client_when_ctx_present_calls_ctx_log() -> None:
    """When ctx is present, log_client calls ctx.log with level and message."""
    ctx = AsyncMock()
    ctx.log = AsyncMock()
    await log_client(ctx, "warning", "client message", logger_name="test.logger")
    ctx.log.assert_awaited_once_with(
        "warning", "client message", logger_name="test.logger"
    )


@pytest.mark.asyncio
async def test_log_client_debug_level_when_ctx_none() -> None:
    """log_client with debug level and no ctx logs at debug."""
    with patch(f"{_CONTEXT_LOGGING_LOGGER}.logger") as mock_logger:
        await log_client(None, "debug", "debug msg")
        mock_logger.debug.assert_called_once_with("debug msg")


@pytest.mark.asyncio
async def test_report_progress_safe_when_ctx_none_is_noop() -> None:
    """report_progress_safe when ctx is None does nothing."""
    await report_progress_safe(None, 50, 100)


@pytest.mark.asyncio
async def test_report_progress_safe_when_ctx_present_calls_report_progress() -> None:
    """report_progress_safe when ctx is present calls ctx.report_progress."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    await report_progress_safe(ctx, 50, 100)
    ctx.report_progress.assert_awaited_once_with(50, 100)


@pytest.mark.asyncio
async def test_report_progress_safe_with_total_none() -> None:
    """report_progress_safe passes total=None when not provided."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    await report_progress_safe(ctx, 25)
    ctx.report_progress.assert_awaited_once_with(25, None)
