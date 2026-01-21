#!/usr/bin/env python3
"""
MCP Memory Bank - Main Entry Point

This is the main entry point for the Memory Bank MCP server.
All tool implementations are in the tools/ package.
"""

import logging
import sys
from builtins import BaseExceptionGroup  # Python 3.11+

import anyio

# Import tools package to register all @mcp.tool() decorators
import cortex.tools  # noqa: F401  # pyright: ignore[reportUnusedImport]
from cortex.server import mcp

logger = logging.getLogger(__name__)


def _is_connection_error(exc: BaseException) -> bool:
    """Check if exception is a connection-related error."""
    if isinstance(
        exc, (anyio.BrokenResourceError, BrokenPipeError, ConnectionResetError)
    ):
        return True
    if isinstance(exc, OSError) and (
        "Broken pipe" in str(exc) or "Connection reset" in str(exc)
    ):
        return True
    # Handle nested exception groups recursively
    if isinstance(exc, BaseExceptionGroup):
        # pyright has issues with BaseExceptionGroup generic type parameter
        # BaseExceptionGroup.exceptions is tuple[BaseException, ...] at runtime
        nested_excs: tuple[BaseException, ...] = exc.exceptions  # type: ignore[assignment]
        for nested in nested_excs:
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
        logger.error(f"MCP server TaskGroup error: {eg}")
        sys.exit(1)
    except (anyio.BrokenResourceError, BrokenPipeError, ConnectionError, OSError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error in MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
