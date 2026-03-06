"""
Shared enums used across validation models.
"""

from enum import Enum


class ValidationSeverity(str, Enum):
    """Validation error severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class QualityHealthStatus(str, Enum):
    """Quality score health status."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class CheckTypeInfrastructure(str, Enum):
    """Check type for infrastructure validation."""

    INFRASTRUCTURE = "infrastructure"


class CheckTypeTimestamps(str, Enum):
    """Check type for timestamp validation."""

    TIMESTAMPS = "timestamps"


__all__ = [
    "ValidationSeverity",
    "QualityHealthStatus",
    "CheckTypeInfrastructure",
    "CheckTypeTimestamps",
]
