#!/usr/bin/env python3
"""MCP server instance for Cortex.

This module provides the FastMCP server instance. While this is technically
global state, it's an acceptable exception as:
1. The FastMCP framework requires a module-level server for tool registration
2. MCP tools are stateless functions that only use this for routing
3. The server itself doesn't hold application state - managers are injected

For proper dependency injection in your own code, use ManagerRegistry instead
of relying on global state.
"""

from mcp.server.fastmcp import FastMCP

# FastMCP server instance (framework requirement)
# This is an acceptable exception to the no-global-state rule
mcp = FastMCP("cortex")
