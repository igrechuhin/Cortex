#!/usr/bin/env python3
"""
MCP Memory Bank - Main Entry Point

This is the main entry point for the Memory Bank MCP server.
All tool implementations are in the tools/ package.
"""

# Import tools package to register all @mcp.tool() decorators
import cortex.tools  # noqa: F401  # pyright: ignore[reportUnusedImport]
from cortex.server import mcp


def main() -> None:
    """Entry point for the application when run with uvx."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
