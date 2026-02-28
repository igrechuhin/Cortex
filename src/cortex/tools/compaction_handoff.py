"""Handoff read/write and progress.txt for session compaction (Phase 56).

Exports: write_handoff, read_handoff. Used by compact_session and session_brief.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from cortex.core.cache_utils import CacheType, get_cache_dir
from cortex.core.file_system import FileSystemManager
from cortex.tools.compaction_constants import (
    SESSION_HANDOFF_FILENAME,
    SESSION_HANDOFF_SCHEMA_VERSION,
    SESSION_PROGRESS_FILENAME,
)
from cortex.tools.models import InProgressTask, SessionHandoff

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HandoffParams:
    """Optional structured params for compact_session handoff."""

    completed_tasks: list[str] | None = None
    in_progress_task: str | None = None
    in_progress_notes: str | None = None
    blockers: list[str] | None = None
    decisions_made: list[str] | None = None


def today_iso() -> str:
    """Return today's date as YYYY-MM-DD."""
    return date.today().strftime("%Y-%m-%d")


def session_id_from_now() -> str:
    """Return session id in format YYYY-MM-DDTHH-MM."""
    return datetime.now().strftime("%Y-%m-%dT%H-%M")


def handoff_path(project_root: Path) -> Path:
    """Path to last_handoff.json under .cortex/.cache/session."""
    session_dir = get_cache_dir(project_root, CacheType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / SESSION_HANDOFF_FILENAME


def _progress_txt_path(project_root: Path) -> Path:
    """Path to progress.txt under .cortex/.cache/session."""
    session_dir = get_cache_dir(project_root, CacheType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / SESSION_PROGRESS_FILENAME


async def write_handoff(
    project_root: Path, handoff: SessionHandoff, fs_manager: FileSystemManager
) -> None:
    """Write session handoff JSON to .cortex/.cache/session/last_handoff.json."""
    path = handoff_path(project_root)
    content = handoff.model_dump_json(indent=2)
    _ = await fs_manager.write_file(path, content, expected_hash=None)


async def read_handoff(
    project_root: Path, fs_manager: FileSystemManager
) -> SessionHandoff | None:
    """Read last session handoff from .cortex/.cache/session/last_handoff.json.

    Returns None if file does not exist or is invalid.
    """
    path = handoff_path(project_root)
    if not path.exists():
        return None
    try:
        content, _ = await fs_manager.read_file(path)
        data = json.loads(content)
        return SessionHandoff.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to read handoff %s: %s", path, e)
        return None


def _progress_section(
    title: str, items: list[str] | None, default: str = "- (none)"
) -> list[str]:
    """Build a ## section with bullet items."""
    out = [f"## {title}"]
    for x in items or []:
        out.append(f"- {x}")
    if not items:
        out.append(default)
    return out


def render_progress_txt(handoff: SessionHandoff) -> str:
    """Render handoff as human-readable progress file (Anthropic Step 5)."""
    lines = [f"# Session Progress - {handoff.session_id}", ""]
    lines.extend(_progress_section("Completed", handoff.completed_tasks))
    lines.append("")
    lines.append("## In Progress")
    if handoff.in_progress:
        lines.append(f"- {handoff.in_progress.task}")
        if handoff.in_progress.notes:
            lines.append(f"  Notes: {handoff.in_progress.notes}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.extend(_progress_section("Next Actions", handoff.next_actions))
    lines.append("")
    lines.extend(_progress_section("Blockers", handoff.blockers))
    if handoff.decisions_made:
        lines.append("")
        lines.extend(_progress_section("Decisions", handoff.decisions_made))
    return "\n".join(lines) + "\n"


async def write_progress_txt(
    project_root: Path,
    handoff: SessionHandoff,
    fs_manager: FileSystemManager,
) -> None:
    """Write human-readable progress file (Anthropic Step 5 structured format)."""
    path = _progress_txt_path(project_root)
    content = render_progress_txt(handoff)
    try:
        _ = await fs_manager.write_file(path, content, expected_hash=None)
    except Exception as e:
        logger.warning("Failed to write progress.txt: %s", e)


def build_handoff(summary: str | None, params: HandoffParams | None) -> SessionHandoff:
    """Build SessionHandoff from summary and optional structured params."""
    hp = params or HandoffParams()
    in_progress: InProgressTask | None = None
    if hp.in_progress_task and hp.in_progress_task.strip():
        in_progress = InProgressTask(
            task=hp.in_progress_task.strip(),
            notes=hp.in_progress_notes.strip() if hp.in_progress_notes else None,
        )
    return SessionHandoff(
        session_id=session_id_from_now(),
        completed_tasks=hp.completed_tasks or [],
        in_progress=in_progress,
        decisions_made=hp.decisions_made or [],
        blockers=hp.blockers or [],
        next_actions=[summary] if summary else [],
        schema_version=SESSION_HANDOFF_SCHEMA_VERSION,
    )


def to_handoff_params(
    completed_tasks: list[str] | None,
    in_progress_task: str | None,
    in_progress_notes: str | None,
    blockers: list[str] | None,
    decisions_made: list[str] | None,
) -> HandoffParams | None:
    """Build HandoffParams if any field is non-empty."""
    if any([completed_tasks, in_progress_task, blockers, decisions_made]):
        return HandoffParams(
            completed_tasks=completed_tasks,
            in_progress_task=in_progress_task,
            in_progress_notes=in_progress_notes,
            blockers=blockers,
            decisions_made=decisions_made,
        )
    return None


async def compact_do_handoff(
    project_root: Path,
    summary: str | None,
    fs_manager: FileSystemManager,
    params: HandoffParams | None = None,
) -> SessionHandoff:
    """Build and write session handoff JSON and progress.txt."""
    handoff = build_handoff(summary, params)
    try:
        await write_handoff(project_root, handoff, fs_manager)
        await write_progress_txt(project_root, handoff, fs_manager)
    except Exception as e:
        logger.warning("Failed to write handoff: %s", e)
    return handoff
