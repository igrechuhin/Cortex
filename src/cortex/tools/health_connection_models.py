"""
Models for check_mcp_connection_health tool results.
"""

from __future__ import annotations

from pydantic import Field

from cortex.core.models import ConnectionHealth, HealthMetrics, OperationStatus

from .models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


class ConnectionHealthResult(ToolResultBase):
    """Result of connection health check."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    health: HealthMetrics


class MCPHealthCheckResponse(StrictBaseModel):
    """Parsed response from check_mcp_connection_health (for parsing only)."""

    status: OperationStatus
    health: ConnectionHealth | None = None
    error: str | None = None
    error_type: str | None = None


class ConnectionHealthErrorResult(ErrorResultBase):
    """Error result for check_mcp_connection_health operations."""


ConnectionHealthResultUnion = ConnectionHealthResult | ConnectionHealthErrorResult
