"""MCP Connection Health Monitoring Tool.

This module provides tools for monitoring MCP connection health and stability.
"""

import json

from cortex.core.mcp_stability import check_connection_health
from cortex.server import mcp


@mcp.tool()
async def check_mcp_connection_health() -> str:
    """Check MCP connection health and resource utilization.

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
