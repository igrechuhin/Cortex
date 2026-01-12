#!/usr/bin/env python3
"""
MCP Memory Bank - Main Entry Point

This is the main entry point for the Memory Bank MCP server.
All tool implementations are in the tools/ package.
"""

import logging
import sys

# Import tools package to register all @mcp.tool() decorators
import cortex.tools  # noqa: F401  # pyright: ignore[reportUnusedImport]
from cortex.server import mcp

logger = logging.getLogger(__name__)


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
    except BrokenPipeError as e:
        logger.warning(f"MCP stdio connection broken (client disconnected): {e}")
        sys.exit(0)  # Exit gracefully - client disconnected
    except ConnectionError as e:
        logger.error(f"MCP connection error: {e}")
        sys.exit(1)
    except OSError as e:
        # Handle BrokenResourceError and other OS-level connection errors
        if "Broken pipe" in str(e) or "Connection reset" in str(e):
            logger.warning(f"MCP connection reset (client disconnected): {e}")
            sys.exit(0)  # Exit gracefully - client disconnected
        logger.error(f"MCP OS error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error in MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
