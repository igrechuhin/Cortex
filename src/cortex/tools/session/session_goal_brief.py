"""Apply session goal anchor to SessionBrief after orientation."""

from __future__ import annotations

from pathlib import Path

from cortex.core.session_goal_builder import build_session_goal
from cortex.core.session_goal_models import SessionGoal
from cortex.core.session_goal_store import read_session_goal, write_session_goal
from cortex.tools.session.models import SessionBrief


def _invalidate_context_cache() -> None:
    from cortex.tools.optimization.handlers import invalidate_context_resource_cache

    invalidate_context_resource_cache()


def _brief_after_write(brief: SessionBrief, sg: SessionGoal) -> SessionBrief:
    return brief.model_copy(
        update={
            "primary_session_goal": sg.goal,
            "session_goal_drift_hint": (
                "Current goal: " + sg.goal + ". Drift detection active."
            ),
        }
    )


def _brief_resumed(brief: SessionBrief, existing: SessionGoal) -> SessionBrief:
    return brief.model_copy(
        update={
            "primary_session_goal": existing.goal,
            "session_goal_drift_hint": (
                "Current goal: "
                + existing.goal
                + ". Drift detection active (resumed from .cortex/.session/session-goal.md)."
            ),
        }
    )


def _brief_no_goal_set(brief: SessionBrief) -> SessionBrief:
    return brief.model_copy(
        update={
            "primary_session_goal": None,
            "session_goal_drift_hint": (
                "No session goal set. Pass goal= to session(operation=start) "
                'or use manage_file(operation="set_goal").'
            ),
        }
    )


def merge_session_goal_into_brief(
    brief: SessionBrief,
    project_root: Path,
    goal: str | None,
    plan_slug: str | None,
    blocked_files: list[str] | None,
) -> SessionBrief:
    """Write or load .cortex/.session/session-goal.md and attach goal lines."""
    if goal and str(goal).strip():
        sg = build_session_goal(
            str(goal).strip(),
            plan_slug.strip() if plan_slug and str(plan_slug).strip() else None,
            project_root,
            blocked_files,
        )
        write_session_goal(project_root, sg)
        _invalidate_context_cache()
        return _brief_after_write(brief, sg)
    existing = read_session_goal(project_root)
    if existing is not None:
        return _brief_resumed(brief, existing)
    return _brief_no_goal_set(brief)
