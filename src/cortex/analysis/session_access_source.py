"""Session-log projection into pattern-analysis access records.

Usage patterns are derived from the `load_context` session logs that Cortex
already writes to `.cortex/.session/context-session-*.json`. Each logged call
records a timestamp, a task description, and the files it selected — which is
exactly file access frequency, co-access, and task-pattern data.
"""

from datetime import datetime, timedelta
from pathlib import Path

from cortex.analysis.pattern_types import AccessRecord
from cortex.core.session_logger import (
    LoadContextLogEntry,
    SessionLog,
    list_session_logs,
    read_session_log,
)


def _records_for_call(
    session_id: str, call_index: int, call: LoadContextLogEntry
) -> list[AccessRecord]:
    """Expand one load_context call into one AccessRecord per selected file."""
    # AI: task_id is synthesised per call because session logs have no task id;
    # session_id + call index is stable across re-reads of the same log.
    task_id = f"{session_id}:{call_index}"
    return [
        AccessRecord(
            timestamp=call.timestamp,
            file=selected,
            task_id=task_id,
            task_description=call.task_description,
            context_files=[f for f in call.selected_files if f != selected],
        )
        for selected in call.selected_files
    ]


def _records_for_log(log: SessionLog, cutoff: str) -> list[AccessRecord]:
    """Project a single session log into access records within the window."""
    records: list[AccessRecord] = []
    for index, call in enumerate(log.load_context_calls):
        if call.timestamp < cutoff:
            continue
        records.extend(_records_for_call(log.session_id, index, call))
    return records


def build_access_records(project_root: Path, window_days: int) -> list[AccessRecord]:
    """Build access records from the project's load_context session logs.

    Args:
        project_root: Project root directory
        window_days: Only calls newer than this many days are projected

    Returns:
        One record per (load_context call, selected file); empty when there is
        no session data. Corrupt or schema-invalid logs are skipped silently.
    """
    # AI: session logs stamp naive local time at minute precision
    # (session_logger.log_load_context_call), so the cutoff must match that
    # format for the lexicographic comparison below to be exact.
    cutoff_dt = datetime.now() - timedelta(days=window_days)
    cutoff = cutoff_dt.isoformat(timespec="minutes")
    # AI: mtime pre-filter keeps construction cheap on projects with hundreds
    # of session logs — a log untouched since the cutoff has no in-window call.
    cutoff_mtime = cutoff_dt.timestamp()

    records: list[AccessRecord] = []
    for log_path in list_session_logs(project_root):
        try:
            if log_path.stat().st_mtime < cutoff_mtime:
                continue
        except OSError:
            continue
        log = read_session_log(log_path)
        if log is None:
            continue
        records.extend(_records_for_log(log, cutoff))
    return records
