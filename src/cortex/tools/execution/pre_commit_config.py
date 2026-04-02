"""Pipeline phase config reading helpers for pre-commit zero-arg tools."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def _merge_task_data(data: object, defaults: dict[str, object]) -> dict[str, object]:
    """Merge parsed JSON task data into defaults, keeping only known keys."""
    if not isinstance(data, dict):
        return defaults
    merged = dict(defaults)
    updates: dict[str, object] = {}
    for k, v in cast(dict[object, object], data).items():
        if isinstance(k, str) and k in defaults:
            updates[k] = v
    merged.update(updates)
    return merged


def read_pipeline_phase_config(
    root: Path,
    pipeline: str,
    phase: str,
    defaults: dict[str, object],
) -> dict[str, object]:
    """Read config for a pipeline phase from its task file. Falls back to defaults."""
    session_id = os.environ.get("CORTEX_SESSION_ID", "")
    if not session_id:
        return defaults
    session_root = get_cortex_path(root, CortexResourceType.SESSION)
    task_path = session_root / session_id / pipeline / f"{phase}-task.json"
    if not task_path.exists():
        return defaults
    try:
        data: object = json.loads(task_path.read_text())
    except (OSError, json.JSONDecodeError):
        return defaults
    return _merge_task_data(data, defaults)


def as_int(value: object, default: int) -> int:
    """Return int value for config scalar input, or default."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def as_float(value: object, default: float) -> float:
    """Return float value for config scalar input, or default."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def as_bool(value: object, default: bool) -> bool:
    """Return bool value for common config inputs, or default."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default
    return default
