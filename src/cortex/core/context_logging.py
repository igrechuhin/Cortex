"""Context-aware logging for MCP tools.

Provides helpers that log to MCP Context when available (client-visible)
and fall back to standard Python logging when Context is not available
(e.g. in tests or non-request code).
"""

import logging
from typing import Literal

from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

logger = logging.getLogger(__name__)

# Public type aliases for use in tool signatures and callers.
LogLevel = Literal["debug", "info", "warning", "error"]
# Context is generic; use ServerSession and object to match SDK get_context().
MCPContext = Context[ServerSession, object]

__all__ = ["LogLevel", "MCPContext", "log_client", "report_progress_safe"]


async def log_client(
    ctx: MCPContext | None,
    level: LogLevel,
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
        level: Log level (debug, info, warning, error).
        message: Log message. Keep client-visible messages short and safe.
        logger_name: Optional logger name for Context logging.
    """
    if ctx is not None:
        await ctx.log(level, message, logger_name=logger_name)
    else:
        getattr(logger, level)(message)


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
        await ctx.report_progress(progress, total)
