"""Session config reader for zero-arg MCP tool fallbacks.

When an MCP client bridge strips all arguments (sends empty {}), tools need
a way to discover their parameters. This module reads a simple JSON file
written by orchestrator prompts at workflow start:

    .cortex/.session/current-task.json

Tools call ``read_session_config()`` to get fallback values for task
description, token budget, pipeline, phase, etc.
"""

from __future__ import annotations

import json
from typing import cast

from pydantic import BaseModel, ConfigDict

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.pydantic_extra import EXTRA_ALLOW
from cortex.core.usage_context import get_current_project_root


class SessionConfig(BaseModel):
    """Structured session config with mapping-style compatibility access."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    task_description: str | None = None
    pipeline: str | None = None
    phase: str | None = None
    operation: str | None = None
    token_budget: int | None = None
    file_name: str | None = None
    check_type: str | None = None
    trace_id: str | None = None
    requirement_id: str | None = None
    selected_step: str | None = None
    workflow_schema: str | None = None
    context_layers: list[str] | None = None

    def _merged_dict(self) -> dict[str, object]:
        data = cast(
            dict[str, object], self.model_dump(mode="python", exclude_none=True)
        )
        if self.model_extra:
            data.update(cast(dict[str, object], self.model_extra))
        return data

    def to_mapping(self) -> dict[str, object]:
        """Return all config keys as a plain mapping."""
        return self._merged_dict()

    def get(self, key: str, default: object | None = None) -> object | None:
        return self._merged_dict().get(key, default)


def read_session_config() -> SessionConfig:
    """Read current task config from session file, or return empty dict.

    Returns a dict with optional keys: task_description, pipeline, phase,
    operation, token_budget, file_name, check_type, trace_id, requirement_id,
    selected_step. All values are strings or ints. ``operation`` is used by
    ``pipeline_handoff`` to recover the intended operation (e.g. "init") when
    an MCP client strips all tool arguments. ``trace_id`` is persisted for structured
    agent logging (see ``cortex.tools.logging``). Optional keys ``reflection`` and
    ``force_reflection`` (booleans) enable the quality gate reflection pass when
    the MCP bridge strips ``run_quality_gate`` arguments.
    """
    root = get_current_project_root()
    if root is None:
        return SessionConfig()
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
    if "context_layers" not in cleaned:
        cleaned["context_layers"] = ["l0", "l1"]
    return SessionConfig.model_validate(cleaned)


def write_session_config(config: SessionConfig | dict[str, object]) -> bool:
    """Write current task config to session file. Returns True on success."""
    root = get_current_project_root()
    if root is None:
        return False
    session_dir = get_cortex_path(root, CortexResourceType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    config_path = session_dir / "current-task.json"
    payload = (
        cast(dict[str, object], config.model_dump(mode="python", exclude_none=True))
        if isinstance(config, SessionConfig)
        else config
    )
    try:
        _ = config_path.write_text(json.dumps(payload, indent=2))
    except OSError:
        return False
    return True
