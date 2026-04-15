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


class TaskType(str, Enum):
    """Task categories used to scope context and rule assembly."""

    ALL = "ALL"
    CORE_LOGIC = "CORE_LOGIC"
    MCP_TOOL = "MCP_TOOL"
    MCP_RESOURCE = "MCP_RESOURCE"
    TEST = "TEST"
    PROMPT = "PROMPT"
    SCHEMA = "SCHEMA"
    INFRA = "INFRA"
    DOCUMENTATION = "DOCUMENTATION"


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
    CORE = "core"
    FOUNDATION = "foundation"
    CONTEXT = "context"
    ACTIVE = "active"
    STATUS = "status"
    TEST = "test"


class RiskLevel(str, Enum):
    """Risk level for consolidation/refactoring."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResponseStatus(str, Enum):
    """Status value for error response model."""

    ERROR = "error"


class PlanStatus(str, Enum):
    """Lifecycle status for a plan file (YAML frontmatter ``status``)."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    READY = "READY"


class PlanningMode(str, Enum):
    """How `/cortex/plan` materializes sections (fast-forward vs human-in-the-loop)."""

    FAST_FORWARD = "ff"
    STEP_BY_STEP = "step"


class PlanSectionStatus(str, Enum):
    """Per-section lifecycle during step-by-step planning."""

    PENDING = "pending"
    DRAFT = "draft"
    APPROVED = "approved"
    SKIPPED = "skipped"


class PlanToolOperation(str, Enum):
    """Discriminator for the unified ``plan()`` MCP tool (internal dispatch)."""

    CREATE = "create"
    LIST = "list"
    GET = "get"
    COMPLETE = "complete"
    REGISTER = "register"
    ENRICH = "enrich"
    GRAPH = "graph"
    ARCHIVE_COMPLETED = "archive_completed"
    CONTINUE_STEP = "continue_step"
    APPROVE_STEP = "approve_step"
    FINALIZE_STEP = "finalize_step"
