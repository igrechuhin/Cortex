"""manage_file operations for `.cortex/.session/session-goal.md`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.core.session_goal_builder import build_session_goal
from cortex.core.session_goal_store import (
    delete_session_goal,
    read_session_goal,
    write_session_goal,
)
from cortex.managers.types import ManagersDict
from cortex.tools.files.operation_helpers import FileOperation


def _invalidate_context_cache() -> None:
    from cortex.tools.optimization.handlers import invalidate_context_resource_cache

    invalidate_context_resource_cache()


def _parse_set_goal_fields(
    payload: dict[str, object],
) -> tuple[str, str | None, list[str]] | str:
    goal_raw = payload.get("goal")
    if not isinstance(goal_raw, str) or not goal_raw.strip():
        return json.dumps(
            {"status": "error", "error": "goal must be a non-empty string"},
            indent=2,
        )
    plan_slug = payload.get("plan_slug")
    plan_slug_s = (
        str(plan_slug).strip() if isinstance(plan_slug, str) and plan_slug else None
    )
    blocked_raw = payload.get("blocked_files")
    blocked: list[str] = []
    if isinstance(blocked_raw, list):
        blocked_list = cast(list[object], blocked_raw)
        blocked = [str(x) for x in blocked_list if str(x).strip()]
    return (goal_raw.strip(), plan_slug_s, blocked)


def _set_goal_from_json(root: Path, content: str) -> str:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return json.dumps(
            {"status": "error", "error": f"Invalid JSON: {e}"},
            indent=2,
        )
    if not isinstance(data, dict):
        return json.dumps(
            {"status": "error", "error": "set_goal content must be a JSON object"},
            indent=2,
        )
    parsed = _parse_set_goal_fields(cast(dict[str, object], data))
    if isinstance(parsed, str):
        return parsed
    goal_text, plan_slug_s, blocked = parsed
    sg = build_session_goal(goal_text, plan_slug_s, root, blocked)
    write_session_goal(root, sg)
    _invalidate_context_cache()
    return json.dumps(
        {
            "status": "success",
            "operation": "set_goal",
            "session_goal": json.loads(sg.model_dump_json()),
        },
        indent=2,
    )


def _clear_goal_json(root: Path) -> str:
    deleted = delete_session_goal(root)
    _invalidate_context_cache()
    return json.dumps(
        {"status": "success", "operation": "clear_goal", "removed": deleted},
        indent=2,
    )


def _get_goal_json(root: Path) -> str:
    sg = read_session_goal(root)
    if sg is None:
        return json.dumps(
            {"status": "success", "operation": "get_goal", "session_goal": None},
            indent=2,
        )
    return json.dumps(
        {
            "status": "success",
            "operation": "get_goal",
            "session_goal": json.loads(sg.model_dump_json()),
        },
        indent=2,
    )


async def execute_session_goal_operation(
    root: Path,
    operation: FileOperation,
    content: str | None,
    _managers: ManagersDict,
) -> str:
    """set_goal / clear_goal / get_goal for session anchoring."""
    if operation == FileOperation.SET_GOAL:
        if content is None or not str(content).strip():
            return json.dumps(
                {"status": "error", "error": "content required for set_goal"},
                indent=2,
            )
        return _set_goal_from_json(root, content)
    if operation == FileOperation.CLEAR_GOAL:
        return _clear_goal_json(root)
    if operation == FileOperation.GET_GOAL:
        return _get_goal_json(root)
    return json.dumps(
        {"status": "error", "error": f"Unsupported goal operation: {operation}"},
        indent=2,
    )
