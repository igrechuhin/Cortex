"""Helpers for building SessionBrief (extracted for file size limit)."""

from __future__ import annotations

from typing import Unpack

from cortex.tools.models import (
    ConcurrentSession,
    GitStatusSummary,
    SessionBrief,
    SessionHandoff,
    SessionHealthSummary,
)
from cortex.tools.session.start_models import SessionBriefContextKwargs


def _create_session_brief(
    project_name: str,
    current_focus: str,
    recent_completed: list[str],
    next_work_item: str | None,
    next_work_plan_path: str | None,
    health: SessionHealthSummary,
    git_status: GitStatusSummary | None,
    session_suggestions: list[str],
    last_handoff: SessionHandoff | None,
    concurrent_sessions: list[ConcurrentSession],
    locked_tasks: list[str],
    mcp_healthy: bool = True,
    mcp_health_message: str | None = None,
) -> SessionBrief:
    """Create SessionBrief from components."""
    return SessionBrief(
        project_name=project_name,
        current_focus=current_focus,
        recent_completed=recent_completed,
        next_work_item=next_work_item,
        next_work_plan_path=next_work_plan_path,
        health=health,
        git_status=git_status,
        session_suggestions=session_suggestions,
        last_handoff=last_handoff,
        concurrent_sessions=concurrent_sessions,
        locked_tasks=locked_tasks,
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
    )


def _create_brief_with_suggestions(
    suggestions: list[str],
    project_name: str,
    current_focus: str,
    recent_completed: list[str],
    next_work_item: str | None,
    next_work_plan_path: str | None,
    health: SessionHealthSummary,
    git_status: GitStatusSummary | None,
    last_handoff: SessionHandoff | None,
    concurrent_sessions: list[ConcurrentSession],
    locked_tasks: list[str],
    mcp_healthy: bool = True,
    mcp_health_message: str | None = None,
) -> SessionBrief:
    """Build SessionBrief from suggestions and components."""
    return _create_session_brief(
        project_name,
        current_focus,
        recent_completed,
        next_work_item,
        next_work_plan_path,
        health,
        git_status,
        suggestions,
        last_handoff,
        concurrent_sessions,
        locked_tasks,
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
    )


def session_brief_context_kwargs(
    project_name: str,
    current_focus: str,
    recent_completed: list[str],
    next_work_item: str | None,
    next_work_plan_path: str | None,
    health: SessionHealthSummary,
    git_status: GitStatusSummary | None,
    last_handoff: SessionHandoff | None,
    concurrent_sessions: list[ConcurrentSession],
    locked_tasks: list[str],
    mcp_healthy: bool = True,
    mcp_health_message: str | None = None,
) -> SessionBriefContextKwargs:
    """Build kwargs for _create_brief_with_suggestions from context."""
    return {
        "project_name": project_name,
        "current_focus": current_focus,
        "recent_completed": recent_completed,
        "next_work_item": next_work_item,
        "next_work_plan_path": next_work_plan_path,
        "health": health,
        "git_status": git_status,
        "last_handoff": last_handoff,
        "concurrent_sessions": concurrent_sessions,
        "locked_tasks": locked_tasks,
        "mcp_healthy": mcp_healthy,
        "mcp_health_message": mcp_health_message,
    }


def brief_from_suggestions_and_context(
    suggestions: list[str],
    **kwargs: Unpack[SessionBriefContextKwargs],
) -> SessionBrief:
    """Build SessionBrief from suggestions and context kwargs."""
    return _create_brief_with_suggestions(suggestions, **kwargs)
