"""Session brief payload capping helpers."""

from __future__ import annotations

from cortex.tools.session.models import ConcurrentSession, SessionBrief

# Bound string fields so session_start tool JSON stays compact and clients cannot choke on
# oversized payloads (mitigates JSONDecodeError / truncation when composing composite tools).
_MAX_SESSION_BRIEF_CONCURRENT_TASK_CHARS = 512
_MAX_SESSION_BRIEF_CURRENT_FOCUS_CHARS = 20000
_MAX_SESSION_BRIEF_LINE_CHARS = 1000
_MAX_SESSION_BRIEF_SUGGESTION_CHARS = 800
_MAX_SESSION_BRIEF_PLAN_GRAPH_SUMMARY_CHARS = 500
_MAX_SESSION_BRIEF_PLAN_GRAPH_ASCII_CHARS = 2500


def _truncate_for_brief_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1] + "…"


def _truncate_optional(value: str | None, max_chars: int) -> str | None:
    if value is None:
        return None
    return _truncate_for_brief_text(value, max_chars)


def _cap_concurrent_session_tasks(
    sessions: list[ConcurrentSession],
) -> list[ConcurrentSession]:
    return [
        ConcurrentSession(
            agent_role=s.agent_role,
            task=_truncate_for_brief_text(
                s.task, _MAX_SESSION_BRIEF_CONCURRENT_TASK_CHARS
            ),
            started=s.started,
            session_id=s.session_id,
        )
        for s in sessions
    ]


def _session_brief_cap_core_fields(brief: SessionBrief, line: int) -> dict[str, object]:
    return {
        "current_focus": _truncate_for_brief_text(
            brief.current_focus, _MAX_SESSION_BRIEF_CURRENT_FOCUS_CHARS
        ),
        "recent_completed": [
            _truncate_for_brief_text(x, line) for x in brief.recent_completed
        ],
        "next_work_item": _truncate_optional(brief.next_work_item, line),
        "next_work_plan_path": _truncate_optional(brief.next_work_plan_path, line),
        "session_suggestions": [
            _truncate_for_brief_text(s, _MAX_SESSION_BRIEF_SUGGESTION_CHARS)
            for s in brief.session_suggestions
        ],
        "concurrent_sessions": _cap_concurrent_session_tasks(brief.concurrent_sessions),
        "locked_tasks": [_truncate_for_brief_text(t, line) for t in brief.locked_tasks],
        "mcp_health_message": _truncate_optional(brief.mcp_health_message, line),
        "gate_feedback_summary": _truncate_optional(brief.gate_feedback_summary, line),
        "clarification_summary": _truncate_optional(brief.clarification_summary, line),
        "constitution_notice": _truncate_optional(brief.constitution_notice, line),
        "primary_session_goal": _truncate_optional(brief.primary_session_goal, line),
        "session_goal_drift_hint": _truncate_optional(
            brief.session_goal_drift_hint, line
        ),
        "plan_graph_summary": _truncate_optional(
            brief.plan_graph_summary, _MAX_SESSION_BRIEF_PLAN_GRAPH_SUMMARY_CHARS
        ),
        "plan_graph_ascii_edges": _truncate_optional(
            brief.plan_graph_ascii_edges, _MAX_SESSION_BRIEF_PLAN_GRAPH_ASCII_CHARS
        ),
    }


def _session_brief_cap_workflow_fields(
    brief: SessionBrief, line: int
) -> dict[str, object]:
    return {
        "workflow_schema_description": _truncate_optional(
            brief.workflow_schema_description, line
        ),
        "workflow_phases": [
            _truncate_for_brief_text(p, line) for p in brief.workflow_phases[:50]
        ],
    }


def _session_brief_cap_update(brief: SessionBrief) -> dict[str, object]:
    """Build ``model_copy(update=...)`` for capped string fields."""
    line = _MAX_SESSION_BRIEF_LINE_CHARS
    merged = _session_brief_cap_core_fields(brief, line)
    merged.update(_session_brief_cap_workflow_fields(brief, line))
    return merged


def cap_session_brief_payload(brief: SessionBrief) -> SessionBrief:
    """Cap long strings in the brief before MCP serialization."""
    return brief.model_copy(update=_session_brief_cap_update(brief))
