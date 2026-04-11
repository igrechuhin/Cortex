"""Session config reader for zero-arg MCP tool fallbacks.

When Cursor's MCP bridge strips all arguments (sends empty {}), tools need
a way to discover their parameters. This module reads a simple JSON file
written by orchestrator prompts at workflow start:

    .cortex/.session/current-task.json

Tools call ``read_session_config()`` to get fallback values for task
description, token budget, pipeline, phase, etc.
"""

from __future__ import annotations

import json
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import get_current_project_root


def read_session_config() -> dict[str, object]:
    """Read current task config from session file, or return empty dict.

    Returns a dict with optional keys: task_description, pipeline, phase,
    operation, token_budget, file_name, check_type, trace_id, requirement_id,
    selected_step. All values are strings or ints. ``operation`` is used by
    ``pipeline_handoff`` to recover the intended operation (e.g. "init") when
    Cursor strips all tool arguments. ``trace_id`` is persisted for structured
    agent logging (see ``cortex.tools.logging``). Optional keys ``reflection`` and
    ``force_reflection`` (booleans) enable the quality gate reflection pass when
    the MCP bridge strips ``run_quality_gate`` arguments.
    """
    root = get_current_project_root()
    if root is None:
        return {}
    session_dir = get_cortex_path(root, CortexResourceType.SESSION)
    config_path = session_dir / "current-task.json"
    cleaned: dict[str, object] = {}
    if config_path.is_file():
        try:
            data: object = json.loads(config_path.read_text())
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            for k, v in cast(dict[object, object], data).items():
                if isinstance(k, str):
                    cleaned[k] = v
    if "workflow_schema" not in cleaned:
        from cortex.core.project_session_config import load_project_session_config

        cleaned["workflow_schema"] = load_project_session_config(root).workflow_schema
    return cleaned


def write_session_config(config: dict[str, object]) -> bool:
    """Write current task config to session file. Returns True on success."""
    root = get_current_project_root()
    if root is None:
        return False
    session_dir = get_cortex_path(root, CortexResourceType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    config_path = session_dir / "current-task.json"
    try:
        _ = config_path.write_text(json.dumps(config, indent=2))
    except OSError:
        return False
    return True
