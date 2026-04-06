"""Unit tests for context_logging module."""

from unittest.mock import AsyncMock, patch

import anyio
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
    ctx.report_progress.assert_awaited_once_with(50, 100, message=None)


@pytest.mark.asyncio
async def test_report_progress_safe_with_total_none() -> None:
    """report_progress_safe passes total=None when not provided."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    await report_progress_safe(ctx, 25)
    ctx.report_progress.assert_awaited_once_with(25, None, message=None)


@pytest.mark.asyncio
async def test_report_progress_safe_forwards_message_when_provided() -> None:
    """report_progress_safe passes message through to ctx.report_progress."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    await report_progress_safe(ctx, 1.0, None, message="..")
    ctx.report_progress.assert_awaited_once_with(1.0, None, message="..")


@pytest.mark.asyncio
async def test_report_progress_safe_message_with_explicit_total() -> None:
    """Optional message works together with a real total (semantic progress)."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    await report_progress_safe(ctx, 3.0, 10.0, message=".")
    ctx.report_progress.assert_awaited_once_with(3.0, 10.0, message=".")


@pytest.mark.asyncio
async def test_log_client_swallows_connection_error_when_ctx_present() -> None:
    """When ctx.log raises connection error (client disconnected), log_client returns without re-raising."""
    ctx = AsyncMock()
    ctx.log = AsyncMock(side_effect=anyio.BrokenResourceError())
    with patch(f"{_CONTEXT_LOGGING_LOGGER}.logger") as mock_logger:
        await log_client(ctx, "info", "msg")
    ctx.log.assert_awaited_once()
    mock_logger.debug.assert_called_once()
    assert "connection closed" in mock_logger.debug.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_report_progress_safe_swallows_connection_error_when_ctx_present() -> (
    None
):
    """When ctx.report_progress raises connection error (client disconnected), report_progress_safe returns without re-raising."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock(side_effect=anyio.BrokenResourceError())
    with patch(f"{_CONTEXT_LOGGING_LOGGER}.logger") as mock_logger:
        await report_progress_safe(ctx, 50, 100)
    ctx.report_progress.assert_awaited_once_with(50, 100, message=None)
    mock_logger.debug.assert_called_once()
    assert "connection closed" in mock_logger.debug.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_log_client_swallows_oserror_broken_pipe() -> None:
    """When ctx.log raises OSError with 'Broken pipe', log_client returns without re-raising."""
    ctx = AsyncMock()
    ctx.log = AsyncMock(side_effect=OSError("Broken pipe"))
    with patch(f"{_CONTEXT_LOGGING_LOGGER}.logger") as mock_logger:
        await log_client(ctx, "info", "msg")
    ctx.log.assert_awaited_once()
    mock_logger.debug.assert_called_once()
    assert "connection closed" in mock_logger.debug.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_log_client_swallows_oserror_connection_reset() -> None:
    """When ctx.log raises OSError with 'Connection reset', log_client returns without re-raising."""
    ctx = AsyncMock()
    ctx.log = AsyncMock(side_effect=OSError("Connection reset"))
    with patch(f"{_CONTEXT_LOGGING_LOGGER}.logger") as mock_logger:
        await log_client(ctx, "info", "msg")
    ctx.log.assert_awaited_once()
    mock_logger.debug.assert_called_once()
    assert "connection closed" in mock_logger.debug.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_report_progress_safe_swallows_oserror_broken_pipe() -> None:
    """When ctx.report_progress raises OSError with 'Broken pipe', report_progress_safe returns without re-raising."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock(side_effect=OSError("Broken pipe"))
    with patch(f"{_CONTEXT_LOGGING_LOGGER}.logger") as mock_logger:
        await report_progress_safe(ctx, 50, 100)
    ctx.report_progress.assert_awaited_once_with(50, 100, message=None)
    mock_logger.debug.assert_called_once()
    assert "connection closed" in mock_logger.debug.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_log_client_re_raises_non_connection_error() -> None:
    """When ctx.log raises a non-connection error, log_client re-raises it."""
    ctx = AsyncMock()
    test_error = ValueError("Test error")
    ctx.log = AsyncMock(side_effect=test_error)
    with pytest.raises(ValueError, match="Test error"):
        await log_client(ctx, "info", "msg")


@pytest.mark.asyncio
async def test_report_progress_safe_re_raises_non_connection_error() -> None:
    """When ctx.report_progress raises a non-connection error, report_progress_safe re-raises it."""
    ctx = AsyncMock()
    test_error = RuntimeError("Test error")
    ctx.report_progress = AsyncMock(side_effect=test_error)
    with pytest.raises(RuntimeError, match="Test error"):
        await report_progress_safe(ctx, 50, 100)
