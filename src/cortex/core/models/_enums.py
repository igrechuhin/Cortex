"""Core enums used across models."""

from enum import Enum


class OperationStatus(str, Enum):
    """Operation result status used by tool and validation result models."""

    SUCCESS = "success"
    ERROR = "error"


class ResponseFormat(str, Enum):
    """Response format for MCP tools that support concise/detailed output."""

    CONCISE = "concise"
    DETAILED = "detailed"


class ContextDepth(str, Enum):
    """Content depth for load_context and context operations."""

    METADATA_ONLY = "metadata_only"
    SUMMARY = "summary"
    FULL = "full"


class HandlerKind(str, Enum):
    """Whether the handler is an MCP tool or resource (Phase 43)."""

    TOOL = "tool"
    RESOURCE = "resource"


class ChangeType(str, Enum):
    """Type of version/snapshot change."""

    CREATED = "created"
    MODIFIED = "modified"
    ROLLBACK = "rollback"
    MANUAL_BACKUP = "manual_backup"


class MigrationResultStatus(str, Enum):
    """Migration execution result status."""

    SUCCESS = "success"
    FAILURE = "failure"


class FileCategory(str, Enum):
    """Context file category in dependency graph."""

    META = "meta"
    FOUNDATION = "foundation"
    CONTEXT = "context"
    ACTIVE = "active"
    STATUS = "status"


class RiskLevel(str, Enum):
    """Risk level for consolidation/refactoring."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResponseStatus(str, Enum):
    """Status value for error response model."""

    ERROR = "error"
