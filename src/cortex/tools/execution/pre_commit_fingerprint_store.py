"""Persistence for the Phase A dirty-state fingerprint.

The Phase A quality gate records its fingerprint in the MCP server process,
but the checks themselves run in a detached worker with a fresh interpreter.
Persisting the fingerprint to the pipeline session directory is what lets the
worker see Phase A's state at all.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, ValidationError

from cortex.tools.execution.session_paths import session_dir

logger = logging.getLogger(__name__)

# Persisted Phase A fingerprint filename inside the pipeline session directory.
_FINGERPRINT_FILENAME = "phase_a_fingerprint.json"

# AI: Hard upper bound on how long a persisted fingerprint may be trusted.
# A stale fingerprint that wrongly matches would skip real checks, so the
# record also pins the git HEAD it was taken at.
_FINGERPRINT_MAX_AGE_SECONDS = 3600.0


class PersistedFingerprint(BaseModel):
    """Phase A fingerprint as persisted to the pipeline session directory."""

    source_hash: str
    all_files_hash: str
    source_file_count: int
    total_file_count: int
    head: str
    recorded_at: float


def fingerprint_path(project_root: Path) -> Path:
    """Path of the persisted Phase A fingerprint for a project."""
    return session_dir(project_root) / _FINGERPRINT_FILENAME


def git_head(project_root: Path) -> str:
    """Return the current git HEAD sha, or empty string when unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def save_fingerprint_record(
    project_root: Path,
    *,
    source_hash: str,
    all_files_hash: str,
    source_file_count: int,
    total_file_count: int,
) -> None:
    """Persist a fingerprint, stamping it with the current HEAD and time.

    HEAD and timestamp are stamped here rather than by the caller so that
    saving and loading read git state through the same code path.
    """
    record = PersistedFingerprint(
        source_hash=source_hash,
        all_files_hash=all_files_hash,
        source_file_count=source_file_count,
        total_file_count=total_file_count,
        head=git_head(project_root),
        recorded_at=time.time(),
    )
    try:
        _ = fingerprint_path(project_root).write_text(record.model_dump_json())
    except OSError:
        logger.warning("Could not persist Phase A fingerprint", exc_info=True)


def clear_phase_a_fingerprint(project_root: Path) -> None:
    """Remove the persisted fingerprint so it cannot leak into a later run."""
    try:
        fingerprint_path(project_root).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not clear Phase A fingerprint", exc_info=True)


def load_fingerprint_record(project_root: Path) -> PersistedFingerprint | None:
    """Load a persisted record, or None when absent, stale, or unreadable.

    Conservative by design: any doubt (missing file, bad JSON, HEAD moved,
    age past the TTL) yields None so checks run rather than being skipped.
    """
    try:
        raw = fingerprint_path(project_root).read_text()
        record = PersistedFingerprint.model_validate(json.loads(raw))
    except (OSError, json.JSONDecodeError, ValidationError):
        return None
    if time.time() - record.recorded_at > _FINGERPRINT_MAX_AGE_SECONDS:
        logger.info("Phase A fingerprint expired; checks will re-run")
        return None
    if record.head != git_head(project_root):
        logger.info("git HEAD moved since Phase A; checks will re-run")
        return None
    return record


__all__ = [
    "PersistedFingerprint",
    "clear_phase_a_fingerprint",
    "fingerprint_path",
    "git_head",
    "load_fingerprint_record",
    "save_fingerprint_record",
]
