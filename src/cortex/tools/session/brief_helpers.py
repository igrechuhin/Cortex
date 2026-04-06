"""Helpers for building SessionBrief (extracted for file size limit)."""

from __future__ import annotations

from cortex.tools.session.models import SESSION_SCOPE_PROMPT, SessionBrief
from cortex.tools.session.start_models import SessionBriefContextKwargs


def _create_session_brief(
    context: SessionBriefContextKwargs,
    session_suggestions: list[str],
) -> SessionBrief:
    """Create SessionBrief from a context model and suggestions list."""
    return SessionBrief(
        project_name=context.project_name,
        current_focus=context.current_focus,
        recent_completed=context.recent_completed,
        next_work_item=context.next_work_item,
        next_work_plan_path=context.next_work_plan_path,
        health=context.health,
        git_status=context.git_status,
        session_suggestions=session_suggestions,
        last_handoff=context.last_handoff,
        concurrent_sessions=context.concurrent_sessions,
        locked_tasks=context.locked_tasks,
        mcp_healthy=context.mcp_healthy,
        mcp_health_message=context.mcp_health_message,
        gate_feedback_summary=context.gate_feedback_summary,
        session_scope=SESSION_SCOPE_PROMPT,
        constitution_notice=context.constitution_notice,
    )


def _create_brief_with_suggestions(
    suggestions: list[str],
    **kwargs: object,
) -> SessionBrief:
    """Build SessionBrief from suggestions and context keyword arguments."""
    context = SessionBriefContextKwargs.model_validate(kwargs)
    return _create_session_brief(context, suggestions)


def brief_from_suggestions_and_context(
    suggestions: list[str],
    context: SessionBriefContextKwargs,
) -> SessionBrief:
    """Build SessionBrief from suggestions and context model."""
    return _create_brief_with_suggestions(
        suggestions,
        # Do not exclude None values here: _create_brief_with_suggestions expects
        # explicit keyword arguments for all fields, including those that may be
        # None (e.g., next_work_plan_path, git_status, last_handoff).
        **context.model_dump(mode="python"),
    )
