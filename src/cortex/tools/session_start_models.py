"""Private types for session_start tool (keeps session_start_tools.py under 400 lines)."""

from __future__ import annotations

from typing import TypedDict

from cortex.tools.models import (
    ConcurrentSession,
    GitStatusSummary,
    SessionHandoff,
    SessionHealthSummary,
)


# Input bundle for _compute_suggestions_and_create_brief (keeps function under 30 lines)
class BriefInputs(TypedDict):
    project_name: str
    current_focus: str
    recent_completed: list[str]
    next_work_item: str | None
    next_work_plan_path: str | None
    health: SessionHealthSummary
    git_status: GitStatusSummary | None
    last_handoff: SessionHandoff | None
    concurrent_sessions: list[ConcurrentSession]
    locked_tasks: list[str]
    mcp_healthy: bool
    mcp_health_message: str | None
