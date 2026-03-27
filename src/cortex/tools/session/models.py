"""
Session, task locking, and session registry result models.

Used by session_start_tools, task_locking, session_registry.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from cortex.core.models import OperationStatus
from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


class TokenBudgetStatus(str, Enum):
    """Token budget health status for session start."""

    HEALTHY = "healthy"
    WARNING = "warning"
    OVER_BUDGET = "over_budget"


class SessionHealthSummary(StrictBaseModel):
    """Quick health check results for session start."""

    file_count: int = Field(ge=0, description="Number of memory bank files")
    total_tokens: int = Field(ge=0, description="Total tokens across all files")
    token_budget_status: TokenBudgetStatus = Field(description="Token budget status")
    missing_files: list[str] = Field(
        default_factory=list, description="Missing required files"
    )
    has_errors: bool = Field(
        default=False, description="Whether critical validation errors exist"
    )


class GitStatusSummary(StrictBaseModel):
    """Git status summary for session start."""

    has_uncommitted_changes: bool = Field(
        description="Whether there are uncommitted changes"
    )
    modified_files_count: int = Field(ge=0, description="Number of modified files")
    untracked_files_count: int = Field(ge=0, description="Number of untracked files")


class InProgressTask(StrictBaseModel):
    """In-progress task from session handoff."""

    task: str = Field(..., min_length=1, description="Task name or description")
    notes: str | None = Field(None, description="Optional notes on progress")


class SessionHandoff(StrictBaseModel):
    """Structured session handoff for next session (JSON-based)."""

    session_id: str = Field(
        ..., min_length=1, description="Session identifier (e.g. 2026-02-11T21:14)"
    )
    completed_tasks: list[str] = Field(
        default_factory=list, description="Tasks completed this session"
    )
    in_progress: InProgressTask | None = Field(
        None, description="Task in progress with optional notes"
    )
    decisions_made: list[str] = Field(
        default_factory=list, description="Key decisions made"
    )
    blockers: list[str] = Field(default_factory=list, description="Current blockers")
    next_actions: list[str] = Field(
        default_factory=list, description="Recommended next actions"
    )
    schema_version: int = Field(
        default=1, ge=1, description="Handoff schema version for compatibility"
    )


class ConcurrentSession(StrictBaseModel):
    """Information about a concurrent agent session."""

    agent_role: str | None = Field(
        None, description="Agent role (feature, quality, testing, etc.)"
    )
    task: str = Field(description="Task title being worked on")
    started: str = Field(description="ISO format datetime when session started")
    session_id: str = Field(description="Unique session identifier")


def _default_concurrent_sessions() -> list[ConcurrentSession]:
    return []


def _default_task_locks() -> list[TaskLock]:
    return []


# Shown on every session start brief so agents adopt single-goal discipline.
SESSION_SCOPE_PROMPT: str = (
    "## Session Scope\n\n"
    "Pick **one** primary goal for this session. Confirm it with the user (or state it clearly) "
    "before taking on additional unrelated work. Single-goal sessions finish more reliably than "
    "mixed bundles of fixes and exploration."
)


class SessionBrief(StrictBaseModel):
    """Session brief with orientation information."""

    project_name: str = Field(description="Project name")
    current_focus: str = Field(
        default="", description="Current focus from activeContext '## Current Focus'"
    )
    recent_completed: list[str] = Field(
        default_factory=list,
        description="Last 3-5 completed items from activeContext",
    )
    next_work_item: str | None = Field(
        None, description="First PENDING item from roadmap"
    )
    next_work_plan_path: str | None = Field(
        None, description="Path to plan file for next work item"
    )
    health: SessionHealthSummary = Field(description="Quick health check results")
    git_status: GitStatusSummary | None = Field(
        None, description="Git status summary if available"
    )
    session_suggestions: list[str] = Field(
        default_factory=list, description="Actionable suggestions for the session"
    )
    last_handoff: SessionHandoff | None = Field(
        None,
        description="Last session handoff from compact_session (if available)",
    )
    concurrent_sessions: list[ConcurrentSession] = Field(
        default_factory=_default_concurrent_sessions,
        description="List of concurrent agent sessions (excluding current session)",
    )
    locked_tasks: list[str] = Field(
        default_factory=list,
        description="List of task titles currently locked by other sessions",
    )
    mcp_healthy: bool = Field(
        default=True,
        description="True if MCP connection health check passed; if False, agent must not proceed",
    )
    mcp_health_message: str | None = Field(
        default=None,
        description="When mcp_healthy is False, short reason (e.g. unhealthy, connection error)",
    )
    session_scope: str = Field(
        default=SESSION_SCOPE_PROMPT,
        min_length=1,
        description=(
            "Session scope guidance: single primary goal, confirm before expanding scope "
            "(markdown/plain text for tool output)"
        ),
    )


class SessionStartResult(ToolResultBase):
    """Result of session_start operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    brief: SessionBrief = Field(description="Session brief with orientation data")
    token_count: int = Field(ge=0, description="Token count of the brief")


class SessionStartErrorResult(ErrorResultBase):
    """Error result for session_start operations."""


SessionStartResultUnion = SessionStartResult | SessionStartErrorResult


class TaskLock(StrictBaseModel):
    """Task lock information."""

    task_id: str = Field(..., min_length=1, description="Unique task identifier")
    task_title: str = Field(..., min_length=1, description="Roadmap entry title")
    agent_session_id: str = Field(
        ..., min_length=1, description="Session ID that holds the lock"
    )
    locked_at: str = Field(
        ..., description="ISO format datetime when lock was acquired"
    )
    expires_at: str = Field(..., description="ISO format datetime when lock expires")
    agent_role: str | None = Field(
        None, description="Agent role (feature, quality, testing, etc.)"
    )
    agent_pid: int | None = Field(
        default=None,
        description="OS process ID that acquired the lock (for stale-lock diagnostics)",
    )


class ClaimTaskResult(StrictBaseModel):
    """Result of claiming a task lock (success)."""

    status: OperationStatus = Field(default=OperationStatus.SUCCESS)
    lock: TaskLock = Field(description="Lock data for the claimed task")
    message: str = Field(description="Success message")


class ClaimTaskErrorResult(ErrorResultBase):
    """Error result for claim_task operations."""

    task_title: str | None = Field(None, description="Task title that failed to lock")


class ReleaseTaskResult(StrictBaseModel):
    """Result of releasing a task lock."""

    status: OperationStatus = Field(description="Operation status")
    task_title: str = Field(description="Task title that was released")
    released: bool = Field(description="Whether lock was successfully released")
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")


class ListActiveTasksResult(StrictBaseModel):
    """Result of listing active task locks."""

    status: OperationStatus = Field(default=OperationStatus.SUCCESS)
    locks: list[TaskLock] = Field(
        default_factory=_default_task_locks, description="List of active task locks"
    )
    count: int = Field(ge=0, description="Number of active locks")


class CheckTaskAvailableResult(StrictBaseModel):
    """Result of checking if a task is available."""

    status: OperationStatus = Field(default=OperationStatus.SUCCESS)
    task_title: str = Field(description="Task title that was checked")
    available: bool = Field(description="Whether task is available (not locked)")
    lock: TaskLock | None = Field(
        None, description="Lock data if task is locked, None if available"
    )


class SessionRegistryResult(StrictBaseModel):
    """Result of session registry operations."""

    status: OperationStatus = Field(description="Operation status")
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")
