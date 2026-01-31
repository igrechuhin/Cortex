#!/usr/bin/env python3
"""
MCP Memory Bank - Main Entry Point

This is the main entry point for the Memory Bank MCP server.
All tool implementations are in the tools/ package.
"""

import asyncio
import logging
import sys
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
        exc, (anyio.BrokenResourceError, BrokenPipeError, ConnectionResetError)
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

    Handles BrokenResourceError, BrokenPipeError, ConnectionResetError,
    and nested exception groups that may contain these errors.

    Args:
        eg: BaseExceptionGroup to check

    Returns:
        True if connection error found (graceful shutdown), False otherwise
    """
    for exc in eg.exceptions:
        if _is_connection_error(exc):
            logger.warning(
                "MCP stdio connection broken during TaskGroup cleanup "
                + f"(client disconnected): {exc}"
            )
            return True
    return False


def _handle_connection_error(e: Exception) -> None:
    """Handle connection-related errors with graceful shutdown.

    Args:
        e: Exception to handle
    """
    if isinstance(e, (anyio.BrokenResourceError, BrokenPipeError)):
        logger.warning(f"MCP stdio connection broken (client disconnected): {e}")
        sys.exit(0)  # Graceful shutdown
    elif isinstance(e, ConnectionError):
        logger.error(f"MCP connection error: {e}")
        sys.exit(1)
    elif isinstance(e, OSError):
        if "Broken pipe" in str(e) or "Connection reset" in str(e):
            logger.warning(f"MCP connection reset (client disconnected): {e}")
            sys.exit(0)  # Exit gracefully - client disconnected
        logger.error(f"MCP OS error: {e}")
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
        # Log first nested exception for debugging tool/server failures
        first = eg.exceptions[0] if eg.exceptions else None
        if first is not None:
            logger.error(
                "MCP server TaskGroup error (%d sub-exception(s)); first: %s",
                len(eg.exceptions),
                first,
                exc_info=(type(first), first, first.__traceback__),
            )
        else:
            logger.error("MCP server TaskGroup error: %s", eg)
        sys.exit(1)
    except (anyio.BrokenResourceError, BrokenPipeError, ConnectionError, OSError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error in MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
