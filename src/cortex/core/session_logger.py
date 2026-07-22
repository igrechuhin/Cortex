"""Session logging for load_context effectiveness analysis.

This module provides logging functionality to track load_context calls
and their results for later analysis and optimization.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.models import DictLikeModel
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.pydantic_extra import EXTRA_FORBID


class LoadContextLogEntry(BaseModel):
    """Structure for a single load_context log entry."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    timestamp: str = Field(description="ISO format timestamp")
    task_description: str = Field(description="Task description")
    token_budget: int = Field(ge=0, description="Token budget")
    strategy: str = Field(description="Loading strategy")
    selected_files: list[str] = Field(
        default_factory=lambda: list[str](),
        description="Selected files",
    )
    selected_sections: dict[str, list[str]] = Field(
        default_factory=lambda: dict[str, list[str]](),
        description="Selected sections by file",
    )
    total_tokens: int = Field(ge=0, description="Total tokens used")
    utilization: float = Field(ge=0.0, le=1.0, description="Token utilization (0-1)")
    excluded_files: list[str] = Field(
        default_factory=lambda: list[str](),
        description="Excluded files",
    )
    relevance_scores: dict[str, float] = Field(
        default_factory=lambda: dict[str, float](),
        description="Relevance scores by file",
    )
    role: str | None = Field(
        default=None,
        description="Agent role (feature/quality/testing/docs/planning/debugging/review)",
    )


class SessionLog(DictLikeModel):
    """Structure for the entire session log."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    session_id: str = Field(description="Session identifier")
    session_start: str = Field(description="Session start timestamp")
    load_context_calls: list[LoadContextLogEntry] = Field(
        default_factory=lambda: list[LoadContextLogEntry](),
        description="List of load_context calls",
    )
    cumulative_spend_tokens: int = Field(
        default=0,
        ge=0,
        description=(
            "Runtime tool-output tokens recorded this session via "
            "record_spend_tokens(); defaults to 0 for log files that "
            "predate this field (backward compatible)."
        ),
    )


def _get_session_id() -> str:
    """Get or create a session ID for the current process.

    Uses environment variable to persist across calls within same session.
    Falls back to generating a new UUID if not set.

    Returns:
        Session ID string (UUID format)
    """
    env_key = "CORTEX_SESSION_ID"
    session_id = os.environ.get(env_key)
    if not session_id:
        session_id = uuid.uuid4().hex[:12]
        os.environ[env_key] = session_id
    return session_id


def _get_session_log_path(project_root: Path) -> Path:
    """Get the path for the current session's log file.

    Args:
        project_root: Project root directory

    Returns:
        Path to the session log JSON file
    """
    session_dir = get_cortex_path(project_root, CortexResourceType.SESSION)
    session_id = _get_session_id()
    return session_dir / f"context-session-{session_id}.json"


def _ensure_session_dir(project_root: Path) -> Path:
    """Ensure the session directory exists.

    Args:
        project_root: Project root directory

    Returns:
        Path to the session directory
    """
    session_dir = get_cortex_path(project_root, CortexResourceType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _fresh_session_log() -> SessionLog:
    """Build a new, empty session log for the current session ID."""
    return SessionLog(
        session_id=_get_session_id(),
        session_start=datetime.now().isoformat(timespec="minutes"),
        load_context_calls=[],
    )


def _load_session_log(log_path: Path) -> SessionLog:
    """Load existing session log or create new one.

    Tolerates a missing, corrupted, or invalid-schema log file by falling
    back to a fresh log rather than raising, so callers (e.g.
    record_spend_tokens) never crash a tool call over stale telemetry.

    Args:
        log_path: Path to the session log file

    Returns:
        Session log dictionary
    """
    if log_path.exists():
        try:
            with open(log_path, encoding="utf-8") as f:
                data = json.load(f)
            return SessionLog.model_validate(data)
        except (json.JSONDecodeError, ValidationError, OSError, UnicodeDecodeError):
            return _fresh_session_log()

    return _fresh_session_log()


def _save_session_log(log_path: Path, session_log: SessionLog) -> None:
    """Save session log to file.

    Args:
        log_path: Path to the session log file
        session_log: Session log model to save
    """
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(session_log.model_dump(), f, indent=2)


def log_load_context_call(
    project_root: Path,
    task_description: str,
    token_budget: int,
    strategy: str,
    selected_files: list[str],
    selected_sections: dict[str, list[str]],
    total_tokens: int,
    utilization: float,
    excluded_files: list[str],
    relevance_scores: dict[str, float],
    role: str | None = None,
) -> None:
    """Log a load_context call for later analysis.

    Args:
        project_root: Project root directory
        task_description: Task description used
        token_budget: Token budget requested
        strategy: Loading strategy used
        selected_files: Files selected by load_context
        selected_sections: Sections selected per file
        total_tokens: Total tokens in selected context
        utilization: Token budget utilization (0.0-1.0)
        excluded_files: Files that were excluded
        relevance_scores: Relevance scores for all files
        role: Optional agent role (feature/quality/testing/docs/planning/debugging/review)
    """
    _ = _ensure_session_dir(project_root)
    log_path = _get_session_log_path(project_root)

    session_log = _load_session_log(log_path)

    entry = LoadContextLogEntry(
        timestamp=datetime.now().isoformat(timespec="minutes"),
        task_description=task_description,
        token_budget=token_budget,
        strategy=strategy,
        selected_files=selected_files,
        selected_sections=selected_sections,
        total_tokens=total_tokens,
        utilization=utilization,
        excluded_files=excluded_files,
        relevance_scores=relevance_scores,
        role=role,
    )

    session_log.load_context_calls.append(entry)
    _save_session_log(log_path, session_log)


def record_spend_tokens(project_root: Path, tokens: int) -> int:
    """Record additional runtime tool-output tokens for the current session.

    Loads the session log (tolerating a missing or corrupted file), adds
    `tokens` to `cumulative_spend_tokens`, persists it, and returns the new
    running total. Call once per instrumented call site with an
    already-computed token count — never re-derive or double count.

    Args:
        project_root: Project root directory
        tokens: Additional tokens to add to the running total (must be >= 0)

    Returns:
        New cumulative_spend_tokens total after recording
    """
    _ = _ensure_session_dir(project_root)
    log_path = _get_session_log_path(project_root)

    session_log = _load_session_log(log_path)
    session_log.cumulative_spend_tokens = session_log.cumulative_spend_tokens + max(
        tokens, 0
    )
    _save_session_log(log_path, session_log)
    return session_log.cumulative_spend_tokens


def get_session_id() -> str:
    """Get the current session ID.

    Returns:
        Current session ID string
    """
    return _get_session_id()


def get_session_log_path(project_root: Path) -> Path:
    """Get the path for the current session's log file.

    Args:
        project_root: Project root directory

    Returns:
        Path to the session log JSON file
    """
    return _get_session_log_path(project_root)


def list_session_logs(project_root: Path) -> list[Path]:
    """List all session log files in the project.

    Args:
        project_root: Project root directory

    Returns:
        List of paths to session log files
    """
    session_dir = get_cortex_path(project_root, CortexResourceType.SESSION)
    if not session_dir.exists():
        return []

    return sorted(session_dir.glob("context-session-*.json"))


def read_session_log(log_path: Path) -> SessionLog | None:
    """Read a session log file.

    Tolerates a corrupted or invalid-schema log file by returning None
    (same as a missing file) rather than raising, since all current callers
    already treat None as "no data available".

    Args:
        log_path: Path to the session log file

    Returns:
        Session log dictionary, or None if the file doesn't exist or is corrupted
    """
    if not log_path.exists():
        return None

    try:
        with open(log_path, encoding="utf-8") as f:
            data = json.load(f)
        return SessionLog.model_validate(data)
    except (json.JSONDecodeError, ValidationError, OSError, UnicodeDecodeError):
        return None
