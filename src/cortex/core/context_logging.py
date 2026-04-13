"""Context-aware logging for MCP tools.

Provides helpers that log to MCP Context when available (client-visible)
and fall back to standard Python logging when Context is not available
(e.g. in tests or non-request code). Connection errors during log/progress
are caught so client disconnect does not propagate (avoids TaskGroup noise).
"""

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Literal, cast

from fastmcp import Context
from mcp.types import LoggingLevel

from cortex.core.mcp_stability_config import is_connection_error

logger = logging.getLogger(__name__)


# Public enum for use in tool signatures and callers.
class LogLevel(str, Enum):
    """Log level for client and fallback logger."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    NOTICE = "notice"
    ERROR = "error"
    CRITICAL = "critical"


# AI: fastmcp.Context is no longer generic in v3; keep MCPContext as direct alias.
MCPContext = Context

__all__ = ["LogLevel", "MCPContext", "log_client", "report_progress_safe"]


async def _log_with_compat(
    ctx: MCPContext, level: LoggingLevel, message: str, logger_name: str | None
) -> None:
    """Call Context.log across FastMCP signature variants.

    inspect.signature on a bound method excludes 'self', so params[0] is
    'message' for the v3 API (message-first) and 'level' for the legacy API.
    """
    log_params = tuple(inspect.signature(ctx.log).parameters.keys())
    if log_params and log_params[0] == "message":
        await ctx.log(message, level=level, logger_name=logger_name)
        return
    legacy_log = cast(Callable[..., Awaitable[None]], ctx.log)
    await legacy_log(level, message, logger_name=logger_name)


async def log_client(
    ctx: MCPContext | None,
    level: LogLevel | str,
    message: str,
    *,
    logger_name: str | None = None,
) -> None:
    """Log to MCP client when ctx is available, else to standard logger.

    Use in tools and helpers that accept optional Context. When ctx is
    present, the message is sent to the client via MCP; when ctx is None,
    the message is logged to stderr via the module logger.

    Args:
        ctx: MCP Context (injected in tools); may be None in helpers or tests.
        level: Log level (debug, info, warning, error) or LogLevel member.
        message: Log message. Keep client-visible messages short and safe.
        logger_name: Optional logger name for Context logging.
    """
    level_str = level.value if isinstance(level, LogLevel) else level
    _level: Literal["debug", "info", "notice", "warning", "error", "critical"] = cast(
        Literal["debug", "info", "notice", "warning", "error", "critical"],
        level_str,
    )
    if ctx is not None:
        try:
            logging_level = cast(LoggingLevel, _level)
            await _log_with_compat(ctx, logging_level, message, logger_name)
        except BaseException as e:
            if isinstance(e, asyncio.CancelledError):
                raise
            if is_connection_error(e):
                logger.debug(
                    "log_client: connection closed (client disconnected); %s",
                    type(e).__name__,
                )
                return
            raise
    else:
        getattr(logger, _level)(message)


async def report_progress_safe(
    ctx: MCPContext | None,
    progress: float,
    total: float | None = None,
    *,
    message: str | None = None,
) -> None:
    """Report progress to the client when ctx is available.

    No-op when ctx is None (e.g. in tests or non-request code).

    Args:
        ctx: MCP Context; may be None.
        progress: Current progress value (e.g. 50).
        total: Optional total value (e.g. 100) for percentage display.
        message: Optional short client-visible status text (e.g. heartbeat dots).
    """
    if ctx is not None:
        try:
            await ctx.report_progress(progress, total, message=message)
        except BaseException as e:
            if isinstance(e, asyncio.CancelledError):
                raise
            if is_connection_error(e):
                logger.debug(
                    "report_progress_safe: connection closed (client disconnected); %s",
                    type(e).__name__,
                )
                return
            raise
