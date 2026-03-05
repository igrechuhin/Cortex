"""Response, connection health, and cache config models."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import CACHE_MAX_SIZE, CACHE_TTL_SECONDS

from ._base import DictLikeModel, JsonDict, ModelDict
from ._enums import ResponseStatus


class ConnectionHealth(DictLikeModel):
    """MCP connection health metrics."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    healthy: bool = Field(description="Whether connection is healthy")
    concurrent_operations: int = Field(
        ge=0, description="Current concurrent operations"
    )
    max_concurrent: int = Field(
        ge=1, description="Maximum allowed concurrent operations"
    )
    semaphore_available: int = Field(ge=0, description="Available semaphore slots")
    utilization_percent: float = Field(
        ge=0.0, le=100.0, description="Resource utilization percentage"
    )
    long_running_holder: str | None = Field(
        default=None,
        description=(
            "Name of tool currently holding the long-running semaphore, or None"
        ),
    )
    degraded: bool = Field(
        default=False,
        description="Whether connection is in degraded mode (circuit breaker open).",
    )
    reconnecting: bool = Field(
        default=False,
        description="Whether a reconnection attempt is currently in progress.",
    )
    reconnect_attempts: int = Field(
        default=0,
        ge=0,
        description="Number of reconnection attempts since last successful connection.",
    )


class MCPToolArguments(BaseModel):
    """Arguments for MCP tool execution."""

    model_config = ConfigDict(extra="allow", validate_assignment=False)


class CacheConfig(BaseModel):
    """Cache configuration settings."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    ttl_seconds: int = Field(default=3600, ge=0, description="Time-to-live in seconds")
    lru_max_size: int = Field(default=100, ge=1, description="LRU cache maximum size")

    def to_dict(self) -> ModelDict:
        """Convert to dictionary for compatibility."""
        return self.model_dump()


class ManagerCacheDefaults(BaseModel):
    """Default cache configurations per manager type."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    token_counter: CacheConfig = Field(
        default_factory=lambda: CacheConfig(ttl_seconds=600, lru_max_size=200),
        description="Token counter cache config",
    )
    file_system: CacheConfig = Field(
        default_factory=lambda: CacheConfig(
            ttl_seconds=CACHE_TTL_SECONDS, lru_max_size=CACHE_MAX_SIZE
        ),
        description="File system cache config",
    )
    dependency_graph: CacheConfig = Field(
        default_factory=lambda: CacheConfig(ttl_seconds=900, lru_max_size=50),
        description="Dependency graph cache config",
    )
    structure_analyzer: CacheConfig = Field(
        default_factory=lambda: CacheConfig(ttl_seconds=1800, lru_max_size=50),
        description="Structure analyzer cache config",
    )
    pattern_analyzer: CacheConfig = Field(
        default_factory=lambda: CacheConfig(ttl_seconds=3600, lru_max_size=100),
        description="Pattern analyzer cache config",
    )

    def get_manager_config(self, manager_name: str) -> CacheConfig:
        """Get cache config for a manager."""
        try:
            return getattr(self, manager_name)
        except AttributeError:
            return self.file_system


class SuccessResponseData(BaseModel):
    """Data for a success response."""

    file_count: int | None = None
    total_tokens: int | None = None
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    def to_dict(self) -> ModelDict:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(exclude_none=True)


class ErrorContext(BaseModel):
    """Context information for error responses."""

    provided_value: int | float | str | None = None
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    def to_dict(self) -> ModelDict:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(exclude_none=True)


class ErrorResponseModel(BaseModel):
    """Complete error response model."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: ResponseStatus = Field(description="Response status")
    error: str = Field(description="Error message")
    error_type: str = Field(description="Error type name")
    action_required: str | None = Field(
        default=None, description="Action required to resolve"
    )
    context: JsonDict | None = Field(default=None, description="Error context")
