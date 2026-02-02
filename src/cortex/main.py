#!/usr/bin/env python3
"""
MCP Memory Bank - Main Entry Point

This is the main entry point for the Memory Bank MCP server.
All tool implementations are in the tools/ package.
"""

import asyncio
import logging
import sys
import traceback
from builtins import BaseExceptionGroup  # Python 3.11+
from typing import cast

import anyio

# Configure logging before FastMCP is created so root has our formatter first.
# FastMCP.__init__ calls configure_logging() → basicConfig(); basicConfig() is a
# no-op when root already has handlers, so we avoid RichHandler column format.
import cortex.core.logging_config  # noqa: F401

# Import tools package to register all @mcp.tool() decorators
import cortex.tools  # noqa: F401
from cortex.server import mcp

cortex.core.logging_config.apply_cortex_format_to_third_party_loggers()

# Explicitly reference cortex.tools to satisfy type checker (imported for side effects)
_ = cortex.tools

logger = logging.getLogger(__name__)


def _is_connection_error(exc: BaseException) -> bool:
    """Check if exception is a connection-related or shutdown-related error."""
    if isinstance(
        exc,
        (
            anyio.BrokenResourceError,
            anyio.ClosedResourceError,
            BrokenPipeError,
            ConnectionResetError,
        ),
    ):
        return True
    if isinstance(exc, asyncio.CancelledError):
        return True  # Task cancellation often means client disconnect or timeout
    if isinstance(exc, OSError) and (
        "Broken pipe" in str(exc) or "Connection reset" in str(exc)
    ):
        return True
    # Handle nested exception groups recursively
    if isinstance(exc, BaseExceptionGroup):
        exc_group = cast(BaseExceptionGroup[BaseException], exc)
        for nested in exc_group.exceptions:
            if _is_connection_error(nested):
                return True
    return False


def _handle_broken_resource_in_group(eg: BaseExceptionGroup) -> bool:
    """Check if BaseExceptionGroup contains connection-related errors.

    Handles BrokenResourceError, ClosedResourceError, BrokenPipeError,
    ConnectionResetError, and nested exception groups that may contain these.

    Args:
        eg: BaseExceptionGroup to check

    Returns:
        True if connection error found (graceful shutdown), False otherwise
    """
    for exc in eg.exceptions:
        if _is_connection_error(exc):
            logger.warning(
                (
                    "MCP stdio connection broken during TaskGroup cleanup "
                    "(client disconnected); group_msg=%s sub_count=%d "
                    "exc_type=%s exc_msg=%s"
                ),
                eg.message,
                len(eg.exceptions),
                type(exc).__name__,
                str(exc),
            )
            return True
    return False


def _handle_connection_error(e: Exception) -> None:
    """Handle connection-related errors with graceful shutdown.

    Args:
        e: Exception to handle
    """
    exc_type = type(e).__name__
    exc_msg = str(e)
    if isinstance(
        e, (anyio.BrokenResourceError, anyio.ClosedResourceError, BrokenPipeError)
    ):
        logger.warning(
            (
                "MCP stdio connection broken or closed (client disconnected); "
                "exc_type=%s exc_msg=%s"
            ),
            exc_type,
            exc_msg,
        )
        sys.exit(0)  # Graceful shutdown
    elif isinstance(e, ConnectionError):
        logger.error("MCP connection error; exc_type=%s exc_msg=%s", exc_type, exc_msg)
        sys.exit(1)
    elif isinstance(e, OSError):
        if "Broken pipe" in exc_msg or "Connection reset" in exc_msg:
            logger.warning(
                (
                    "MCP connection reset (client disconnected); "
                    "exc_type=%s exc_msg=%s"
                ),
                exc_type,
                exc_msg,
            )
            sys.exit(0)  # Exit gracefully - client disconnected
        logger.error("MCP OS error; exc_type=%s exc_msg=%s", exc_type, exc_msg)
        sys.exit(1)


def _log_exception_with_traceback(exc: BaseException, prefix: str = "") -> None:
    """Log a single exception with full traceback; recurse into exception groups."""
    if isinstance(exc, BaseExceptionGroup):
        nested = cast(BaseExceptionGroup[BaseException], exc)
        for i, sub in enumerate(nested.exceptions):
            _log_exception_with_traceback(sub, prefix=f"{prefix}[{i}] ")
        return
    lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb_text = "".join(lines).strip()
    logger.error("%sMCP TaskGroup sub-exception: %s\n%s", prefix, exc, tb_text)


def _log_and_exit_on_task_group_error(eg: BaseExceptionGroup) -> None:
    """Log TaskGroup error details (including full nested tracebacks) and exit with code 1."""
    sub_summary = "; ".join(
        f"{type(e).__name__}: {str(e)[:200]}" for e in eg.exceptions[:5]
    )
    if len(eg.exceptions) > 5:
        sub_summary += f" ... and {len(eg.exceptions) - 5} more"
    logger.error(
        (
            "MCP server TaskGroup error (not connection-related); "
            "group_msg=%s sub_count=%d sub_exceptions=[%s]"
        ),
        eg.message,
        len(eg.exceptions),
        sub_summary,
    )
    for i, exc in enumerate(eg.exceptions):
        _log_exception_with_traceback(exc, prefix=f"[{i}] ")
    sys.exit(1)


def main() -> None:
    """Entry point for the application when run with uvx.

    Handles MCP stdio connection with improved error handling and stability.
    Provides comprehensive error handling for connection issues and ensures
    graceful shutdown on errors.
    """
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("MCP server interrupted by user")
        sys.exit(0)
    except BaseExceptionGroup as eg:
        if _handle_broken_resource_in_group(eg):
            sys.exit(0)  # Graceful shutdown
        _log_and_exit_on_task_group_error(eg)
    except (
        anyio.BrokenResourceError,
        anyio.ClosedResourceError,
        BrokenPipeError,
        ConnectionError,
        OSError,
    ) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error in MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
