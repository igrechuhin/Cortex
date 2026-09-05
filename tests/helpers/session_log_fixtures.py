"""Session-log fixtures for pattern-analysis tests.

`PatternAnalyzer` projects its access log from `.cortex/.session/` load_context
logs at construction time, so tests seed logs with these helpers *before*
building the analyzer.
"""

from datetime import datetime, timedelta
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.session_logger import LoadContextLogEntry, SessionLog

SessionCall = tuple[str, str, list[str]]
"""One load_context call: (timestamp, task_description, selected_files)."""


def recent_stamp(minutes_ago: int = 0) -> str:
    """Build a session-log timestamp in the log's naive-local minute format."""
    return (datetime.now() - timedelta(minutes=minutes_ago)).isoformat(
        timespec="minutes"
    )


def write_session_log(
    project_root: Path, session_id: str, calls: list[SessionCall]
) -> Path:
    """Write a session log fixture with the given load_context calls.

    Args:
        project_root: Project root directory
        session_id: Session identifier used in the file name
        calls: (timestamp, task_description, selected_files) per call

    Returns:
        Path to the written session log
    """
    session_dir = get_cortex_path(project_root, CortexResourceType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    log_path = session_dir / f"context-session-{session_id}.json"
    session_log = SessionLog(
        session_id=session_id,
        session_start=calls[0][0] if calls else recent_stamp(),
        load_context_calls=[
            LoadContextLogEntry(
                timestamp=timestamp,
                task_description=description,
                token_budget=1000,
                strategy="balanced",
                selected_files=selected_files,
                total_tokens=500,
                utilization=0.5,
            )
            for timestamp, description, selected_files in calls
        ],
    )
    _ = log_path.write_text(session_log.model_dump_json(), encoding="utf-8")
    return log_path


def seed_accesses(
    project_root: Path, session_id: str, file_groups: list[list[str]]
) -> Path:
    """Seed one recent load_context call per file group.

    Args:
        project_root: Project root directory
        session_id: Session identifier used in the file name
        file_groups: Files selected together, one group per call

    Returns:
        Path to the written session log
    """
    calls: list[SessionCall] = [
        (recent_stamp(len(file_groups) - index), f"task-{index}", files)
        for index, files in enumerate(file_groups)
    ]
    return write_session_log(project_root, session_id, calls)
