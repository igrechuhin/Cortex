"""Pydantic models for MCP tool usage tracking (Phase 29)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolUsageEvent(BaseModel):
    """Single tool usage event for analytics."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(description="Name of the MCP tool invoked")
    timestamp: str = Field(description="ISO 8601 timestamp")
    duration_ms: float = Field(ge=0, description="Execution duration in milliseconds")
    success: bool = Field(description="Whether the tool completed without error")
    error_type: str | None = Field(
        default=None, description="Exception type name if failed"
    )
    params_hash: str | None = Field(
        default=None, description="Hash of anonymized parameters for deduplication"
    )
    handler_kind: Literal["tool", "resource"] = Field(
        default="tool",
        description="Whether the handler is an MCP tool or resource (Phase 43)",
    )


class ToolUsageStats(BaseModel):
    """Aggregated usage statistics for a tool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(description="Name of the MCP tool")
    total_calls: int = Field(ge=0, description="Total number of calls")
    successful_calls: int = Field(ge=0, description="Number of successful calls")
    failed_calls: int = Field(ge=0, description="Number of failed calls")
    avg_duration_ms: float = Field(ge=0, description="Average duration in milliseconds")
    min_duration_ms: float = Field(ge=0, description="Minimum duration in milliseconds")
    max_duration_ms: float = Field(ge=0, description="Maximum duration in milliseconds")
    error_types: dict[str, int] = Field(
        default_factory=dict, description="Error type name to count"
    )
    first_used: str = Field(description="ISO 8601 timestamp of first use")
    last_used: str = Field(description="ISO 8601 timestamp of last use")
