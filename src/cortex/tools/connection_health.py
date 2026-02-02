"""MCP Connection Health Monitoring Tool.

This module provides tools for monitoring MCP connection health and stability.
"""

import json

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    check_connection_health,
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.server import mcp


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=read_only_annotations(
        "Check MCP Connection Health",
        idempotent=False,
    ),  # pyright: ignore[reportCallIssue]
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def check_mcp_connection_health() -> str:
    """Check MCP connection health and resource utilization.

    USE WHEN: User wants connection status, user needs health check,
    user requests connection health, user wants to monitor MCP server.

    EXAMPLES: 'check MCP connection health', 'get connection status',
    'check server health', 'monitor MCP connection'.

    RETURNS: JSON with connection status, resource metrics, and health
    indicators.

    Returns connection health metrics including:
    - Connection status (healthy/unhealthy)
    - Current concurrent operations
    - Maximum allowed concurrent operations
    - Resource utilization percentage
    - Available semaphore slots

    Returns:
        JSON string with health metrics:
        {
          "status": "success",
          "health": {
            "healthy": true,
            "concurrent_operations": 2,
            "max_concurrent": 5,
            "semaphore_available": 3,
            "utilization_percent": 40.0
          }
        }

    Example:
        >>> check_mcp_connection_health()
        {
          "status": "success",
          "health": {
            "healthy": true,
            "concurrent_operations": 1,
            "max_concurrent": 5,
            "semaphore_available": 4,
            "utilization_percent": 20.0
          }
        }
    """
    try:
        health = await check_connection_health()
        return json.dumps(
            {
                "status": "success",
                "health": health.model_dump(),
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            },
            indent=2,
        )
