"""Trace id, requirement id, and git head for structured agent logs."""

from __future__ import annotations

import subprocess
from uuid import uuid4

from cortex.core.session_config import read_session_config, write_session_config


def read_git_head_short() -> str | None:
    """Return abbreviated git HEAD hash, or None if unavailable."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    line = completed.stdout.strip()
    return line if line else None


def ensure_trace_id_persisted() -> str:
    """Return ``trace_id`` from session config, creating and persisting one if missing."""
    cfg = read_session_config()
    raw = cfg.get("trace_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    new_id = uuid4().hex[:12]
    merged: dict[str, object]
    if isinstance(cfg, dict):
        merged = dict(cfg)
    else:
        merged = cfg.to_mapping()
    merged["trace_id"] = new_id
    _ = write_session_config(merged)
    return new_id


def get_agent_log_context() -> tuple[str, str | None, str | None]:
    """Return ``(trace_id, requirement_id, commit_hash)`` for :class:`LogEvent` fields."""
    trace_id = ensure_trace_id_persisted()
    cfg = read_session_config()
    req_raw = cfg.get("requirement_id")
    if not isinstance(req_raw, str) or not req_raw.strip():
        step_raw = cfg.get("selected_step")
        req_raw = step_raw if isinstance(step_raw, str) else None
    requirement_id = (
        req_raw.strip() if isinstance(req_raw, str) and req_raw.strip() else None
    )
    commit_hash = read_git_head_short()
    return trace_id, requirement_id, commit_hash
