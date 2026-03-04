"""Context-aware logging for MCP tools.

Provides helpers that log to MCP Context when available (client-visible)
and fall back to standard Python logging when Context is not available
(e.g. in tests or non-request code). Connection errors during log/progress
are caught so client disconnect does not propagate (avoids TaskGroup noise).
"""

import asyncio
import logging
from enum import Enum
from typing import Literal, cast

from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from cortex.core.mcp_stability_config import is_connection_error

logger = logging.getLogger(__name__)


# Public enum for use in tool signatures and callers.
class LogLevel(str, Enum):
    """Log level for client and fallback logger."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# Context is generic; use ServerSession and object to match SDK get_context().
MCPContext = Context[ServerSession, object]

__all__ = ["LogLevel", "MCPContext", "log_client", "report_progress_safe"]


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
    _level: Literal["debug", "info", "warning", "error"] = cast(
        Literal["debug", "info", "warning", "error"], level_str
    )
    if ctx is not None:
        try:
            await ctx.log(_level, message, logger_name=logger_name)
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
) -> None:
    """Report progress to the client when ctx is available.

    No-op when ctx is None (e.g. in tests or non-request code).

    Args:
        ctx: MCP Context; may be None.
        progress: Current progress value (e.g. 50).
        total: Optional total value (e.g. 100) for percentage display.
    """
    if ctx is not None:
        try:
            await ctx.report_progress(progress, total)
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
