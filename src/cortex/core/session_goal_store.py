"""Read/write `.cortex/.session/session-goal.md` (JSON body) for session anchoring."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.session_goal_models import SessionGoal

SESSION_GOAL_FILENAME = "session-goal.md"


def session_goal_path(project_root: Path) -> Path:
    """Ephemeral goal file under `.cortex/.session/` (not memory-bank)."""
    return (
        get_cortex_path(project_root, CortexResourceType.SESSION)
        / SESSION_GOAL_FILENAME
    )


def read_session_goal(project_root: Path) -> SessionGoal | None:
    """Load session goal if present and valid."""
    path = session_goal_path(project_root)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return SessionGoal.model_validate(data)
    except Exception:
        return None


def write_session_goal(project_root: Path, goal: SessionGoal) -> None:
    """Persist session goal JSON to disk."""
    path = session_goal_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # AI: trailing newline keeps the .md-suffixed file MD047-clean, so a session
    # start does not fail the markdown lint leg of the quality gate.
    _ = path.write_text(
        goal.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def delete_session_goal(project_root: Path) -> bool:
    """Remove session goal file. Returns True if a file was removed."""
    path = session_goal_path(project_root)
    if not path.is_file():
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False
